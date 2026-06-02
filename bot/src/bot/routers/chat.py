import asyncio
import base64
import logging
from io import BytesIO

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.types import BufferedInputFile, Message

from src.core.config import settings
from src.services import api_client as api
from src.utils.formatting import convert_to_markdownv2
from src.utils.localization import t
from src.utils.stickers import monkey

logger = logging.getLogger(__name__)
router = Router()

# Per-user concurrency control
user_semaphores: dict[int, asyncio.Semaphore] = {}
user_tasks: dict[int, asyncio.Task] = {}

_VISION_MODELS = {"gpt-4o", "gpt-5-nano", "gpt-5-mini"}
_PARSE_MODE_MAP = {"html": "HTML", "markdown": "Markdown", "markdown_v2": "MarkdownV2"}

# Cached bot meta (username / id) — populated on first group message
_bot_username: str | None = None
_bot_id: int | None = None


async def _get_bot_meta(bot: Bot) -> tuple[str | None, int | None]:
    global _bot_username, _bot_id
    if _bot_username is None:
        info = await bot.get_me()
        _bot_username = info.username
        _bot_id = info.id
    return _bot_username, _bot_id


def _get_semaphore(user_id: int) -> asyncio.Semaphore:
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(1)
    return user_semaphores[user_id]


async def _is_busy(user_id: int, message: Message, language: str) -> bool:
    if _get_semaphore(user_id).locked():
        await message.reply(t("wait_for_previous", language), parse_mode="HTML")
        return True
    return False


async def _is_bot_mentioned(message: Message, bot: Bot) -> bool:
    """In private chats always True. In groups: @mention or reply-to-bot."""
    if message.chat.type == ChatType.PRIVATE:
        return True
    try:
        username, bot_id = await _get_bot_meta(bot)
        text = message.text or message.caption or ""
        if username and f"@{username}" in text:
            return True
        if message.reply_to_message and message.reply_to_message.from_user:
            return message.reply_to_message.from_user.id == bot_id
    except Exception:
        return True
    return False


def _mode_name(chat_mode: str, lang: str) -> str:
    template = settings.chat_modes.get(chat_mode, {}).get("name", chat_mode)
    if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
        return t(template.strip("{}"), lang)
    return template or chat_mode


def _last_user_text_from_dialog_entry(user_msg) -> str:
    """Extract plain-text prompt from a dialog message's user field."""
    if isinstance(user_msg, list):
        for item in user_msg:
            if item.get("type") == "text":
                return item.get("text", "")
        return ""
    return str(user_msg or "")


def _mode_welcome(chat_mode: str, lang: str) -> str:
    template = settings.chat_modes.get(chat_mode, {}).get("welcome_message", "")
    if not template:
        return ""
    if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
        return t(template.strip("{}"), lang)
    return template


@router.message(Command("new"), StateFilter("*"))
async def cmd_new(message: Message, language: str) -> None:
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    user = await api.get_user(user_id)
    if user is None:
        return
    chat_mode = user.current_chat_mode
    await api.start_new_dialog(user_id)

    await message.answer(t("new_chat_started", language))
    welcome = _mode_welcome(chat_mode, language)
    if welcome:
        await message.answer(welcome, parse_mode="HTML")


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, language: str) -> None:
    user_id = message.from_user.id
    task = user_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
    else:
        await message.answer(t("nothing_to_cancel", language), parse_mode="HTML")


@router.message(Command("retry"), StateFilter("*"))
async def cmd_retry(message: Message, language: str, bot: Bot, db_user=None) -> None:
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    if db_user is None:
        db_user = await api.get_user(user_id)
    if db_user is None:
        await message.answer(t("no_retry_messages", language))
        return

    try:
        ensure = await api.ensure_dialog(user_id)
    except Exception as exc:
        logger.error("Retry: ensure_dialog failed for user %d: %s", user_id, exc, exc_info=True)
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("error_message", language).format(exc), parse_mode="HTML")
        return

    dialog_id = ensure.dialog_id
    dialog_messages = list(ensure.messages)
    if not dialog_messages:
        await message.answer(t("no_retry_messages", language))
        return

    last = dialog_messages[-1]
    text = _last_user_text_from_dialog_entry(last.get("user", ""))
    if not text.strip():
        await message.answer(t("no_retry_messages", language))
        return

    image_buffer: BytesIO | None = None
    user_msg = last.get("user", "")
    if isinstance(user_msg, list):
        for item in user_msg:
            if item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:image/jpeg;base64,"):
                    try:
                        raw = base64.b64decode(url.replace("data:image/jpeg;base64,", ""))
                        image_buffer = BytesIO(raw)
                        image_buffer.name = "image.jpg"
                    except Exception:
                        logger.warning("Failed to decode retry image for user %d", user_id)

    try:
        await api.set_dialog_messages(user_id, dialog_messages[:-1], dialog_id=dialog_id)
    except Exception as exc:
        logger.error("Retry: set_dialog_messages failed for user %d: %s", user_id, exc, exc_info=True)
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("error_message", language).format(exc), parse_mode="HTML")
        return

    await _run_handle(message, bot, language, user_id, text, image_buffer)


async def generate_image(
    message: Message,
    bot: Bot,
    language: str,
    user_id: int,
    prompt: str,
) -> None:
    await monkey.send(bot, message.chat.id, "generating")
    await bot.send_chat_action(message.chat.id, "upload_photo")

    try:
        image_buffers, imgbb_urls = await api.generate_images(
            prompt,
            n_images=settings.return_n_generated_images,
            size=settings.image_size,
            quality=settings.image_quality,
            user_id=user_id,
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = e.response.text
        if status in (400, 422) and ("content_policy_violation" in body or "moderation_blocked" in body):
            await monkey.send(bot, message.chat.id, "sad")
            await message.answer(t("image_generation_rejected", language), parse_mode="HTML")
        elif status == 429:
            await monkey.send(bot, message.chat.id, "sad")
            await message.answer(t("rate_limit_error", language), parse_mode="HTML")
        else:
            await monkey.send(bot, message.chat.id, "error")
            await message.answer(t("image_generation_error", language).format(e), parse_mode="HTML")
        logger.error("Image generation HTTP %d for user %d: %s", status, user_id, body)
        return
    except Exception as e:
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("image_generation_error", language).format(e), parse_mode="HTML")
        logger.error("Image generation failed for user %d: %s", user_id, e)
        return

    for img_buf in image_buffers:
        await bot.send_chat_action(message.chat.id, "upload_photo")
        await message.answer_photo(BufferedInputFile(img_buf.read(), filename="image.png"))

    # Persist prompt so /retry can regenerate (artist mode does not use /chat/complete).
    # Use ImgBB URL if available so the image appears in the gallery alongside mini-app images.
    saved_url = next((u for u in imgbb_urls if u), "[generated_image]")
    try:
        ensure = await api.ensure_dialog(user_id)
        messages = list(ensure.messages)
        messages.append({"user": prompt, "bot": saved_url})
        await api.set_dialog_messages(user_id, messages, dialog_id=ensure.dialog_id)
    except Exception:
        logger.warning("Failed to save image prompt for /retry (user %d)", user_id, exc_info=True)

    await monkey.send(bot, message.chat.id, "happy")

async def _handle_text_or_vision(
    message: Message,
    bot: Bot,
    language: str,
    user_id: int,
    text: str,
    image_buffer: BytesIO | None = None,
) -> None:
    # Parallel: fetch user (Redis cache) and ensure dialog + load messages simultaneously.
    user, ensure_result = await asyncio.gather(
        api.get_user(user_id),
        api.ensure_dialog(user_id),
    )
    if user is None:
        return

    chat_mode = user.current_chat_mode
    if chat_mode not in settings.chat_modes:
        chat_mode = "assistant"
    current_model = user.current_model
    dialog_id = ensure_result.dialog_id
    # Limit context to last 20 messages to prevent token overflow
    dialog_messages = ensure_result.messages[-20:]

    if chat_mode == "artist":
        await generate_image(message, bot, language, user_id, text)
        return

    await bot.send_chat_action(message.chat.id, "typing")

    if not text.strip():
        await message.answer(t("empty_message", language), parse_mode="HTML")
        return

    raw_pm = settings.chat_modes.get(chat_mode, {}).get("parse_mode", "html")
    parse_mode = _PARSE_MODE_MAP.get(raw_pm, "HTML")

    image_b64: str | None = None
    if image_buffer is not None:
        image_buffer.seek(0)
        image_b64 = base64.b64encode(image_buffer.read()).decode()

    n_input_tokens = n_output_tokens = 0
    n_first_removed = 0
    answer = ""
    is_flagged = False
    streaming_msg = None

    try:
        if settings.enable_message_streaming:
            # SSE stream from API
            is_private = message.chat.type == ChatType.PRIVATE
            streaming_msg = None
            prev_edit_len = 0

            if is_private:
                # If a processing sticker is already shown, do not send the ⏳ emoji
                if not monkey._processing.get(message.chat.id):
                    try:
                        streaming_msg = await message.answer(
                            '<tg-emoji emoji-id="5841359499146825803">⏳</tg-emoji>',
                            parse_mode="HTML"
                        )
                    except Exception as exc:
                        logger.debug("Could not send streaming placeholder (user %d): %s", user_id, exc)

            async for chunk in api.chat_stream(
                user_id=user_id, dialog_id=dialog_id, message=text, dialog_messages=dialog_messages,
                chat_mode=chat_mode, model=current_model, image_b64=image_b64,
            ):
                if chunk.is_flagged:
                    is_flagged = True
                    break
                answer = chunk.text
                n_input_tokens = chunk.n_input_tokens
                n_output_tokens = chunk.n_output_tokens
                n_first_removed = chunk.n_first_removed

                if chunk.status == "not_finished":
                    if streaming_msg is None and is_private and answer.strip():
                        try:
                            streaming_msg = await message.answer(answer)
                            prev_edit_len = len(answer)
                        except Exception as exc:
                            logger.debug("Could not send initial streaming message (user %d): %s", user_id, exc)
                    elif streaming_msg is not None:
                        if abs(len(answer) - prev_edit_len) >= 50:
                            try:
                                await bot.edit_message_text(
                                    chat_id=message.chat.id,
                                    message_id=streaming_msg.message_id,
                                    text=answer,
                                )
                                prev_edit_len = len(answer)
                            except Exception as exc:
                                logger.debug("edit_message_text stream error (user %d): %s", user_id, exc)
        else:
            # Non-streaming
            streaming_msg = None
            result = await api.chat_complete(
                user_id=user_id, dialog_id=dialog_id, message=text, dialog_messages=dialog_messages,
                chat_mode=chat_mode, model=current_model, image_b64=image_b64,
            )
            is_flagged = result.is_flagged
            answer = result.answer
            n_first_removed = result.n_first_removed

        if is_flagged:
            await monkey.send(bot, message.chat.id, "sad")
            await message.answer(t("content_moderation_failed", language), parse_mode="HTML")
            return

        answer = answer[:4096]
        final_raw = answer.strip()
        if parse_mode == "MarkdownV2":
            final_text = convert_to_markdownv2(final_raw)
        elif parse_mode == "HTML":
            final_text = final_raw
        else:
            final_text = final_raw

        if streaming_msg is not None:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=streaming_msg.message_id,
                    text=final_text,
                    parse_mode=parse_mode,
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    pass
                else:
                    try:
                        await bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=streaming_msg.message_id,
                            text=final_raw,
                        )
                    except TelegramBadRequest as e2:
                        if "message is not modified" not in str(e2):
                            try:
                                await bot.delete_message(message.chat.id, streaming_msg.message_id)
                            except Exception:
                                pass
                            await message.answer(final_raw)
            except Exception:
                try:
                    await bot.delete_message(message.chat.id, streaming_msg.message_id)
                except Exception:
                    pass
                await message.answer(final_raw)
        else:
            try:
                await message.answer(final_text, parse_mode=parse_mode)
            except Exception:
                await message.answer(final_raw, parse_mode=None)

    except asyncio.CancelledError:
        if streaming_msg is not None:
            try:
                await bot.delete_message(message.chat.id, streaming_msg.message_id)
            except Exception:
                pass
        await monkey.send(bot, message.chat.id, "sad")
        raise

    except Exception as exc:
        if streaming_msg is not None:
            try:
                await bot.delete_message(message.chat.id, streaming_msg.message_id)
            except Exception:
                pass
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("error_message", language).format(exc), parse_mode="HTML")
        logger.error("Message handle error for user %d: %s", user_id, exc, exc_info=True)
        return

    if n_first_removed == 1:
        await message.answer(t("context_message_removed_one", language), parse_mode="HTML")
    elif n_first_removed > 1:
        await message.answer(
            t("context_messages_removed_many", language).format(n_first_removed),
            parse_mode="HTML",
        )

    await monkey.delete_processing(bot, message.chat.id)


async def _run_handle(
    message: Message,
    bot: Bot,
    language: str,
    user_id: int,
    text: str,
    image_buffer: BytesIO | None = None,
) -> None:
    """Acquire per-user semaphore, store task ref, run core handler."""
    sem = _get_semaphore(user_id)
    async with sem:
        user_tasks[user_id] = asyncio.current_task()
        try:
            await _handle_text_or_vision(
                message, bot, language, user_id, text, image_buffer,
            )
        except asyncio.CancelledError:
            await message.answer(t("operation_cancelled", language), parse_mode="HTML")
        finally:
            user_tasks.pop(user_id, None)
            # Удаляем семафор если никто больше не ждёт на нём — иначе dict растёт вечно
            sem_obj = user_semaphores.get(user_id)
            if sem_obj is not None and not sem_obj._waiters:  # type: ignore[attr-defined]
                user_semaphores.pop(user_id, None)

@router.message(F.text & ~F.text.startswith("/"), StateFilter(None))
async def msg_text(message: Message, language: str, bot: Bot) -> None:
    if not await _is_bot_mentioned(message, bot):
        return
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    text = message.text or ""
    if message.chat.type != ChatType.PRIVATE:
        username, _ = await _get_bot_meta(bot)
        if username:
            text = text.replace(f"@{username}", "").strip()

    await _run_handle(message, bot, language, user_id, text)


@router.message(F.photo, StateFilter(None))
async def msg_photo(message: Message, language: str, bot: Bot) -> None:
    if not await _is_bot_mentioned(message, bot):
        return
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    await monkey.send(bot, message.chat.id, "thinking")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    buf = BytesIO()
    await bot.download_file(file.file_path, buf)
    buf.name = "image.jpg"
    buf.seek(0)

    text = message.caption or ""
    if message.chat.type != ChatType.PRIVATE:
        username, _ = await _get_bot_meta(bot)
        if username:
            text = text.replace(f"@{username}", "").strip()
    if not text:
        text = t("photo_default_prompt", language)

    await _run_handle(message, bot, language, user_id, text, image_buffer=buf)


@router.message(F.voice, StateFilter(None))
async def msg_voice(message: Message, language: str, bot: Bot) -> None:
    if not await _is_bot_mentioned(message, bot):
        return
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    await monkey.send(bot, message.chat.id, "thinking")

    voice = message.voice
    file = await bot.get_file(voice.file_id)
    buf = BytesIO()
    await bot.download_file(file.file_path, buf)
    buf.name = "voice.oga"
    buf.seek(0)

    try:
        transcribed, _ = await api.transcribe_audio(buf, user_id=user_id, lang=language)
    except Exception as exc:
        logger.error("Voice transcription failed for user %d: %s", user_id, exc, exc_info=True)
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("voice_recognition_failed", language), parse_mode="HTML")
        return

    if not transcribed:
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("voice_recognition_failed", language), parse_mode="HTML")
        return

    await _run_handle(message, bot, language, user_id, transcribed)


@router.message(
    F.document | F.video | F.audio | F.sticker | F.animation,
    StateFilter("*"),
)
async def msg_unsupported(message: Message, language: str) -> None:
    await message.answer(t("unsupported_media", language))


@router.edited_message(F.text | F.photo, StateFilter("*"))
async def msg_edited(message: Message, language: str) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(t("edited_message_unsupported", language), parse_mode="HTML")