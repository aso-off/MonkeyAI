import base64
import logging
from io import BytesIO
from typing import AsyncGenerator

import tiktoken
from openai import AsyncOpenAI, BadRequestError

from core.config import settings

logger = logging.getLogger(__name__)

_tiktoken_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _tiktoken_encoding
    if _tiktoken_encoding is None:
        _tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
    return _tiktoken_encoding


BASE_OPTIONS: dict = {
    "timeout": 60.0,
}

MODEL_OPTIONS: dict[str, dict] = {
    "gpt-5-mini": {
        "max_completion_tokens": 8192,
        "reasoning_effort": "medium",
    },
    "gpt-4o": {
        "max_completion_tokens": 4000,
        "temperature": 0.3,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    },
    "gpt-5-nano": {
        "max_completion_tokens": 8192,
        "reasoning_effort": "low",
    },
}

MODEL_FAMILY: dict[str, str] = {
    "gpt-5-nano": "gpt-5-nano",
    "gpt-4o": "gpt-4o",
    "gpt-5-mini": "gpt-5-mini",
}

_openai_client: AsyncOpenAI | None = None


def make_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        if settings.openai_api_base:
            _openai_client.base_url = settings.openai_api_base
    return _openai_client


def _encode_image(image_buffer: BytesIO) -> str:
    pos = image_buffer.tell()
    image_buffer.seek(0)
    encoded = base64.b64encode(image_buffer.read()).decode("utf-8")
    image_buffer.seek(pos)
    return encoded


class ChatGPT:
    def __init__(self, model: str = "gpt-5-nano") -> None:
        if model not in MODEL_FAMILY:
            raise ValueError(f"Unknown model: {model!r}. Available: {sorted(MODEL_FAMILY)}")
        self.model = model
        self.client = make_client()

    def _options(self) -> dict:
        family = MODEL_FAMILY.get(self.model, self.model)
        options = BASE_OPTIONS.copy()
        options.update(MODEL_OPTIONS.get(family, {}))
        return options

    def _build_messages(
        self,
        message: str,
        dialog_messages: list,
        chat_mode: str,
        image_buffer: BytesIO | None = None,
    ) -> list:
        system_prompt = settings.chat_modes.get("system_prompt", "")
        mode_prompt = settings.chat_modes[chat_mode].get("prompt_start", "")
        if system_prompt and mode_prompt:
            prompt = f"{system_prompt}\n{mode_prompt}"
        else:
            prompt = system_prompt or mode_prompt
        messages = [{"role": "system", "content": prompt}] if prompt else []

        for dm in dialog_messages:
            messages.append({"role": "user", "content": dm["user"]})
            messages.append({"role": "assistant", "content": dm["bot"]})

        if image_buffer is not None:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode_image(image_buffer)}",
                        "detail": "high",
                    }},
                ],
            })
        else:
            messages.append({"role": "user", "content": message})

        return messages

    def _count_tokens(self, messages: list, answer: str) -> tuple[int, int]:
        try:
            encoding = _get_encoding()
            tokens_per_message = 100 if self.model == "gpt-5-mini" else 50
            tokens_per_name = -1 if self.model == "gpt-5-mini" else 1

            n_input = 0
            for msg in messages:
                n_input += tokens_per_message
                for key, value in msg.items():
                    if isinstance(value, str):
                        n_input += len(encoding.encode(value))
                    if key == "name":
                        n_input += tokens_per_name

            n_output = len(encoding.encode(answer))
            return n_input + n_output, n_output
        except Exception:
            logger.warning("Token counting failed, using estimate", exc_info=True)
            return 500, len(answer) // 4

    def _validate_mode(self, chat_mode: str) -> None:
        valid_modes = {k for k in settings.chat_modes if k != "system_prompt"}
        if chat_mode not in valid_modes:
            raise ValueError(f"Chat mode {chat_mode!r} is not supported")

    async def send_message(
        self,
        message: str,
        dialog_messages: list | None = None,
        chat_mode: str = "assistant",
    ) -> tuple[str, tuple[int, int], int]:
        dialog_messages = list(dialog_messages or [])
        self._validate_mode(chat_mode)
        n_before = len(dialog_messages)

        while True:
            try:
                messages = self._build_messages(message, dialog_messages, chat_mode)
                r = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **self._options(),
                )
                answer = r.choices[0].message.content or ""
                answer = answer.strip()
                if not answer:
                    raise ValueError("Model returned an empty response. Please try again.")
                return answer, (r.usage.prompt_tokens, r.usage.completion_tokens), n_before - len(dialog_messages)
            except BadRequestError:
                if not dialog_messages:
                    raise ValueError("Dialog reduced to zero but still exceeds token limit")
                dialog_messages = dialog_messages[1:]

    async def send_message_stream(
        self,
        message: str,
        dialog_messages: list | None = None,
        chat_mode: str = "assistant",
    ) -> AsyncGenerator[tuple[str, str, tuple[int, int], int], None]:
        dialog_messages = list(dialog_messages or [])
        self._validate_mode(chat_mode)
        n_before = len(dialog_messages)
        n_input = n_output = 0

        while True:
            try:
                messages = self._build_messages(message, dialog_messages, chat_mode)
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    **self._options(),
                )
                answer = ""
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        answer += delta.content
                        yield "not_finished", answer, (n_input, n_output), 0

                answer = answer.strip()
                if not answer:
                    raise ValueError("Model returned an empty response. Please try again.")
                n_input, n_output = self._count_tokens(messages, answer)
                yield "finished", answer, (n_input, n_output), n_before - len(dialog_messages)
                return
            except BadRequestError:
                if not dialog_messages:
                    raise
                dialog_messages = dialog_messages[1:]

    async def send_vision_message(
        self,
        message: str,
        dialog_messages: list | None = None,
        chat_mode: str = "assistant",
        image_buffer: BytesIO | None = None,
    ) -> tuple[str, tuple[int, int], int]:
        dialog_messages = list(dialog_messages or [])
        n_before = len(dialog_messages)

        while True:
            try:
                messages = self._build_messages(message, dialog_messages, chat_mode, image_buffer)
                r = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **self._options(),
                )
                answer = r.choices[0].message.content or ""
                answer = answer.strip()
                if not answer:
                    raise ValueError("Model returned an empty response. Please try again.")
                return answer, (r.usage.prompt_tokens, r.usage.completion_tokens), n_before - len(dialog_messages)
            except BadRequestError:
                if not dialog_messages:
                    raise ValueError("Dialog reduced to zero but still exceeds token limit")
                dialog_messages = dialog_messages[1:]

    async def send_vision_message_stream(
        self,
        message: str,
        dialog_messages: list | None = None,
        chat_mode: str = "assistant",
        image_buffer: BytesIO | None = None,
    ) -> AsyncGenerator[tuple[str, str, tuple[int, int], int], None]:
        dialog_messages = list(dialog_messages or [])
        n_before = len(dialog_messages)
        n_input = n_output = 0

        while True:
            try:
                messages = self._build_messages(message, dialog_messages, chat_mode, image_buffer)
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    **self._options(),
                )
                answer = ""
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        answer += delta.content
                        yield "not_finished", answer, (n_input, n_output), n_before - len(dialog_messages)

                answer = answer.strip()
                if not answer:
                    raise ValueError("Model returned an empty response. Please try again.")
                n_input, n_output = self._count_tokens(messages, answer)
                yield "finished", answer, (n_input, n_output), n_before - len(dialog_messages)
                return
            except BadRequestError:
                if not dialog_messages:
                    raise
                dialog_messages = dialog_messages[1:]
