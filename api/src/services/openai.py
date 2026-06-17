import base64
import logging
from io import BytesIO
from typing import AsyncGenerator

from openai import AsyncOpenAI, BadRequestError

from core.config import settings

logger = logging.getLogger(__name__)

BASE_OPTIONS: dict = {
    "timeout": 60.0,
}


def _text_models() -> list[str]:
    return settings.models.get("available_text_models", []) or []


def _model_options(model: str) -> dict:
    info = settings.models.get("info", {}).get(model, {}) or {}
    return info.get("options", {}) or {}

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


def _to_responses_item(message: dict) -> dict:
    role = message["role"]
    content = message["content"]
    if isinstance(content, str):
        return {"role": role, "content": content}
    parts: list = []
    for p in content:
        if p.get("type") == "text":
            parts.append({"type": "input_text", "text": p.get("text", "")})
        elif p.get("type") == "image_url":
            iu = p.get("image_url", {})
            parts.append({
                "type": "input_image",
                "image_url": iu.get("url", ""),
                "detail": iu.get("detail", "auto"),
            })
    return {"role": role, "content": parts}


class ChatGPT:
    def __init__(self, model: str = "gpt-5.4-nano") -> None:
        available = _text_models()
        if model not in available:
            raise ValueError(f"Unknown model: {model!r}. Available: {sorted(available)}")
        self.model = model
        self.client = make_client()

    def _options(self) -> dict:
        options = BASE_OPTIONS.copy()
        options.update(_model_options(self.model))
        return options

    def _responses_options(self) -> dict:
        raw = self._options()
        # не храним ответы на стороне OpenAI; truncation=auto — канон-обрезка под окно
        opts: dict = {"store": False, "truncation": "auto"}
        if "timeout" in raw:
            opts["timeout"] = raw["timeout"]
        if "max_completion_tokens" in raw:
            opts["max_output_tokens"] = raw["max_completion_tokens"]
        for k in ("temperature", "top_p"):
            if k in raw:
                opts[k] = raw[k]
        if "reasoning_effort" in raw:
            opts["reasoning"] = {"effort": raw["reasoning_effort"], "summary": "auto"}
        return opts

    def _build_responses_input(
        self,
        message: str,
        dialog_messages: list,
        chat_mode: str,
        image_buffer: BytesIO | None = None,
        image_url: str | None = None,
    ) -> tuple[str, list]:
        messages = self._build_messages(message, dialog_messages, chat_mode, image_buffer, image_url)
        instructions = ""
        items: list = []
        for m in messages:
            if m["role"] == "system" and isinstance(m["content"], str):
                instructions = m["content"]
                continue
            items.append(_to_responses_item(m))
        return instructions, items

    def _build_messages(
        self,
        message: str,
        dialog_messages: list,
        chat_mode: str,
        image_buffer: BytesIO | None = None,
        image_url: str | None = None,
    ) -> list:
        system_prompt = settings.chat_modes.get("system_prompt", "")
        mode_prompt = settings.chat_modes[chat_mode].get("prompt_start", "")
        if system_prompt and mode_prompt:
            prompt = f"{system_prompt}\n{mode_prompt}"
        else:
            prompt = system_prompt or mode_prompt
        messages = [{"role": "system", "content": prompt}] if prompt else []

        for dm in dialog_messages:
            messages.append({"role": dm["role"], "content": dm["content"]})

        if image_url is not None:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "auto"}},
                ],
            })
        elif image_buffer is not None:
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
    ) -> AsyncGenerator[tuple[str, str, str, tuple[int, int], int], None]:
        dialog_messages = list(dialog_messages or [])
        self._validate_mode(chat_mode)
        n_input = n_output = 0

        instructions, input_items = self._build_responses_input(message, dialog_messages, chat_mode)
        stream = await self.client.responses.create(
            model=self.model,
            instructions=instructions or None,
            input=input_items,
            stream=True,
            **self._responses_options(),
        )
        answer = ""
        reasoning = ""
        async for event in stream:
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                answer += event.delta
                yield "not_finished", answer, reasoning, (n_input, n_output), 0
            elif etype == "response.reasoning_summary_text.delta":
                reasoning += event.delta
                yield "not_finished", answer, reasoning, (n_input, n_output), 0
            elif etype == "response.completed":
                usage = getattr(event.response, "usage", None)
                if usage:
                    n_input, n_output = usage.input_tokens, usage.output_tokens

        answer = answer.strip()
        if not answer:
            raise ValueError("Model returned an empty response. Please try again.")
        if not (n_input or n_output):
            logger.warning("Stream ended without usage for model %s", self.model)
        yield "finished", answer, reasoning, (n_input, n_output), 0

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
        image_url: str | None = None,
    ) -> AsyncGenerator[tuple[str, str, str, tuple[int, int], int], None]:
        dialog_messages = list(dialog_messages or [])
        n_input = n_output = 0

        instructions, input_items = self._build_responses_input(
            message, dialog_messages, chat_mode, image_buffer, image_url
        )
        stream = await self.client.responses.create(
            model=self.model,
            instructions=instructions or None,
            input=input_items,
            stream=True,
            **self._responses_options(),
        )
        answer = ""
        reasoning = ""
        async for event in stream:
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                answer += event.delta
                yield "not_finished", answer, reasoning, (n_input, n_output), 0
            elif etype == "response.reasoning_summary_text.delta":
                reasoning += event.delta
                yield "not_finished", answer, reasoning, (n_input, n_output), 0
            elif etype == "response.completed":
                usage = getattr(event.response, "usage", None)
                if usage:
                    n_input, n_output = usage.input_tokens, usage.output_tokens

        answer = answer.strip()
        if not answer:
            raise ValueError("Model returned an empty response. Please try again.")
        if not (n_input or n_output):
            logger.warning("Stream ended without usage for model %s", self.model)
        yield "finished", answer, reasoning, (n_input, n_output), 0