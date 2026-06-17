import asyncio
import base64
import logging
import time
from io import BytesIO
from typing import TYPE_CHECKING

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.types import BufferedInputFile, InputRichMessage, Message, ReplyParameters
from src.core.config import settings

if TYPE_CHECKING:
    from src.core.bot import RedisAsync
from src.services import api_client as api
from src.utils import rich_builder as rich
from src.utils.formatting import convert_to_markdownv2
from src.utils.localization import t
from src.utils.stickers import monkey

logger = logging.getLogger(__name__)
router = Router()

# отмена — только в своём воркере
user_tasks: dict[int, asyncio.Task] = {}

# распределённый лок «занят»
_BUSY_LOCK_PREFIX = "chat:busy:"

# id последнего ответа — для редактирования при /retry
_LAST_ANSWER_PREFIX = "chat:last_answer:"
_LAST_ANSWER_TTL = 172800  # 48ч — лимит редактирования Telegram

_PARSE_MODE_MAP = {"html": "HTML", "markdown": "Markdown", "markdown_v2": "MarkdownV2"}

_bot_username: str | None = None
_bot_id: int | None = None


def set_bot_meta(username: str | None, bot_id: int | None) -> None:
    global _bot_username, _bot_id
    _bot_username = username
    _bot_id = bot_id


async def _get_bot_meta(bot: Bot) -> tuple[str | None, int | None]:
    global _bot_username, _bot_id
    if _bot_username is None:
        info = await bot.get_me()
        _bot_username = info.username
        _bot_id = info.id
    return _bot_username, _bot_id


def _redis() -> "RedisAsync":
    from src.core.bot import fsm_redis

    return fsm_redis()


async def _store_answer_id(user_id: int, message_id: int) -> None:
    await _redis().set(f"{_LAST_ANSWER_PREFIX}{user_id}", str(message_id), ex=_LAST_ANSWER_TTL)


async def _get_answer_id(user_id: int) -> int | None:
    val = await _redis().get(f"{_LAST_ANSWER_PREFIX}{user_id}")
    if val is None:
        return None
    if isinstance(val, bytes):
        val = val.decode()
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def _is_busy(user_id: int, message: Message, language: str) -> bool:
    if await _redis().exists(f"{_BUSY_LOCK_PREFIX}{user_id}"):
        await _reply(message, t("wait_for_previous", language))
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


def _reply_to(message: Message) -> ReplyParameters:
    return ReplyParameters(message_id=message.message_id, allow_sending_without_reply=True)


async def _reply(message: Message, text: str, parse_mode: str | None = "HTML") -> None:
    await message.answer(text, parse_mode=parse_mode, reply_parameters=_reply_to(message))


async def _send_rich(message: Message, rich_msg: InputRichMessage) -> int | None:
    reply = _reply_to(message)
    effect = settings.message_effect_id or None
    attempts = (
        lambda: message.answer_rich(rich_message=rich_msg, reply_parameters=reply, message_effect_id=effect),
        lambda: message.answer_rich(rich_message=rich_msg, reply_parameters=reply),
        lambda: message.answer_rich(rich_message=rich_msg),
    )
    for call in attempts:
        try:
            sent = await call()
            return sent.message_id
        except Exception as exc:
            logger.warning("answer_rich failed (chat %s): %s", message.chat.id, exc)
    return None


async def _send_legacy(message: Message, final_raw: str, parse_mode: str) -> None:
    final_text = convert_to_markdownv2(final_raw) if parse_mode == "MarkdownV2" else final_raw
    rp = _reply_to(message)
    try:
        await message.answer(final_text, parse_mode=parse_mode, reply_parameters=rp)
    except Exception:
        await message.answer(final_raw, parse_mode=None, reply_parameters=rp)


@router.message(Command("new"), StateFilter("*"))
async def cmd_new(message: Message, language: str) -> None:
    if message.from_user is None:
        return
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
    if message.from_user is None:
        return
    user_id = message.from_user.id
    task = user_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
    else:
        await message.answer(t("nothing_to_cancel", language), parse_mode="HTML")


@router.message(Command("retry"), StateFilter("*"))
async def cmd_retry(message: Message, language: str, bot: Bot, db_user=None) -> None:
    if message.from_user is None:
        return
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
        last_user_msg = await api.pop_last_exchange(user_id, dialog_id=ensure.dialog_id)
    except Exception as exc:
        logger.error("Retry failed for user %d: %s", user_id, exc, exc_info=True)
        await monkey.send(bot, message.chat.id, "error")
        await message.answer(t("error_message", language).format(exc), parse_mode="HTML")
        return

    if last_user_msg is None:
        await message.answer(t("no_retry_messages", language))
        return

    content = last_user_msg.get("content", "")
    text = _last_user_text_from_dialog_entry(content)
    if not text.strip():
        await message.answer(t("no_retry_messages", language))
        return

    image_buffer: BytesIO | None = None
    if isinstance(content, list):
        for item in content:
            if item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:image/jpeg;base64,"):
                    try:
                        raw = base64.b64decode(url.replace("data:image/jpeg;base64,", ""))
                        image_buffer = BytesIO(raw)
                        image_buffer.name = "image.jpg"
                    except Exception:
                        logger.warning("Failed to decode retry image for user %d", user_id)

    edit_message_id = await _get_answer_id(user_id)
    await _run_handle(message, bot, language, user_id, text, image_buffer, edit_message_id=edit_message_id)


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
            await _reply(message, t("image_generation_rejected", language))
        elif status == 429:
            await monkey.send(bot, message.chat.id, "sad")
            await _reply(message, t("rate_limit_error", language))
        else:
            await monkey.send(bot, message.chat.id, "error")
            await _reply(message, t("image_generation_error", language).format(e))
        logger.error("Image generation HTTP %d for user %d: %s", status, user_id, body)
        return
    except Exception as e:
        await monkey.send(bot, message.chat.id, "error")
        await _reply(message, t("image_generation_error", language).format(e))
        logger.error("Image generation failed for user %d: %s", user_id, e)
        return

    for img_buf in image_buffers:
        await bot.send_chat_action(message.chat.id, "upload_photo")
        await message.answer_photo(
            BufferedInputFile(img_buf.read(), filename="image.png"),
            reply_parameters=_reply_to(message),
        )

    # чтобы работал /retry; ImgBB-URL — для галереи
    saved_url = next((u for u in imgbb_urls if u), "[generated_image]")
    try:
        ensure = await api.ensure_dialog(user_id)
        await api.append_exchange(user_id, prompt, saved_url, dialog_id=ensure.dialog_id)
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
    edit_message_id: int | None = None,
) -> int | None:
    user, ensure_result = await asyncio.gather(
        api.get_user(user_id),
        api.ensure_dialog(user_id),
    )
    if user is None:
        return None

    chat_mode = user.current_chat_mode
    if chat_mode not in settings.chat_modes:
        chat_mode = "assistant"
    current_model = user.current_model
    dialog_id = ensure_result.dialog_id

    if chat_mode == "artist":
        await generate_image(message, bot, language, user_id, text)
        return

    await bot.send_chat_action(message.chat.id, "typing")

    if not text.strip():
        await _reply(message, t("empty_message", language))
        return None

    raw_pm = settings.chat_modes.get(chat_mode, {}).get("parse_mode", "html")
    parse_mode = _PARSE_MODE_MAP.get(raw_pm, "HTML")
    use_rich = settings.enable_rich_messages and message.chat.type == ChatType.PRIVATE
    draft_enabled = use_rich and edit_message_id is None

    image_b64: str | None = None
    if image_buffer is not None:
        image_buffer.seek(0)
        image_b64 = base64.b64encode(image_buffer.read()).decode()

    answer = ""
    is_flagged = False

    try:
        if settings.enable_message_streaming:
            draft_id = message.message_id
            last_draft = 0.0
            last_think = 0.0
            reasoning = ""
            show_thinking = (
                draft_enabled
                and settings.enable_thinking_block
                and rich.is_reasoning_model(current_model, settings.models)
            )

            # индикатор сразу — у reasoning есть латентность, а сводка может и не прийти
            if show_thinking:
                try:
                    await bot.send_rich_message_draft(
                        chat_id=message.chat.id,
                        draft_id=draft_id,
                        rich_message=rich.thinking_draft(t("thinking", language)),
                    )
                except Exception as exc:
                    logger.debug("thinking draft error (user %d): %s", user_id, exc)
                last_think = time.monotonic()

            async for chunk in api.chat_stream(
                user_id=user_id,
                dialog_id=dialog_id,
                message=text,
                chat_mode=chat_mode,
                model=current_model,
                image_b64=image_b64,
            ):
                if chunk.is_flagged:
                    is_flagged = True
                    break
                answer = chunk.text
                if chunk.reasoning:
                    reasoning = chunk.reasoning

                # rich-черновик только в ЛС и не при редактировании
                if not draft_enabled or chunk.status != "not_finished":
                    continue

                now = time.monotonic()
                if not answer.strip():
                    if show_thinking and reasoning and now - last_think >= settings.draft_throttle_seconds:
                        try:
                            await bot.send_rich_message_draft(
                                chat_id=message.chat.id,
                                draft_id=draft_id,
                                rich_message=rich.thinking_draft(t("thinking", language), reasoning),
                            )
                            last_think = now
                        except Exception as exc:
                            logger.debug("thinking draft error (user %d): %s", user_id, exc)
                    continue

                if now - last_draft >= settings.draft_throttle_seconds:
                    try:
                        await bot.send_rich_message_draft(
                            chat_id=message.chat.id,
                            draft_id=draft_id,
                            rich_message=rich.build_draft(answer, settings.rich_message_max_length),
                        )
                        last_draft = now
                    except Exception as exc:
                        logger.debug("send_rich_message_draft stream error (user %d): %s", user_id, exc)
        else:
            result = await api.chat_complete(
                user_id=user_id,
                dialog_id=dialog_id,
                message=text,
                chat_mode=chat_mode,
                model=current_model,
                image_b64=image_b64,
            )
            is_flagged = result.is_flagged
            answer = result.answer

        if is_flagged:
            await monkey.send(bot, message.chat.id, "sad")
            await _reply(message, t("content_moderation_failed", language))
            return None

        if not answer.strip():
            await monkey.send(bot, message.chat.id, "error")
            await _reply(message, t("error_response", language))
            return None

        limit = settings.rich_message_max_length if use_rich else settings.message_max_length
        final_raw = answer[:limit].strip()

        sent_id: int | None = None
        # финал заменяет черновик
        if use_rich:
            rich_msg = rich.build_message(final_raw, settings.rich_message_max_length)
            if edit_message_id is not None:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=edit_message_id,
                        rich_message=rich_msg,
                    )
                    sent_id = edit_message_id
                except Exception as exc:
                    logger.warning("edit rich failed (user %d), sending new: %s", user_id, exc)
            if sent_id is None:
                sent_id = await _send_rich(message, rich_msg)
            if sent_id is None:
                logger.warning("rich send failed (user %d), fallback to legacy", user_id)
                await _send_legacy(message, final_raw[: settings.message_max_length], parse_mode)
        else:
            await _send_legacy(message, final_raw, parse_mode)

    except asyncio.CancelledError:
        await monkey.send(bot, message.chat.id, "sad")
        raise

    except Exception as exc:
        await monkey.send(bot, message.chat.id, "error")
        await _reply(message, t("error_message", language).format(exc))
        logger.error("Message handle error for user %d: %s", user_id, exc, exc_info=True)
        return None

    await monkey.delete_processing(bot, message.chat.id)
    return sent_id


async def _run_handle(
    message: Message,
    bot: Bot,
    language: str,
    user_id: int,
    text: str,
    image_buffer: BytesIO | None = None,
    edit_message_id: int | None = None,
) -> None:
    """Acquire the distributed busy lock, store task ref, run core handler."""
    lock_key = f"{_BUSY_LOCK_PREFIX}{user_id}"
    # TTL — страховка от зависания
    acquired = await _redis().set(lock_key, "1", nx=True, ex=settings.busy_lock_ttl_seconds)
    if not acquired:
        await _reply(message, t("wait_for_previous", language))
        return

    task = asyncio.current_task()
    if task is not None:
        user_tasks[user_id] = task
    try:
        sent_id = await _handle_text_or_vision(
            message,
            bot,
            language,
            user_id,
            text,
            image_buffer,
            edit_message_id=edit_message_id,
        )
        if sent_id is not None:
            await _store_answer_id(user_id, sent_id)
    except asyncio.CancelledError:
        await _reply(message, t("operation_cancelled", language))
    finally:
        user_tasks.pop(user_id, None)
        await _redis().delete(lock_key)


@router.message(F.text & ~F.text.startswith("/"), StateFilter(None))
async def msg_text(message: Message, language: str, bot: Bot) -> None:
    if not await _is_bot_mentioned(message, bot):
        return
    if message.from_user is None:
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
    if message.from_user is None:
        return
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    if not message.photo:
        return
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > settings.max_upload_mb * 1024 * 1024:
        await _reply(message, t("file_too_large", language).format(settings.max_upload_mb))
        return

    await monkey.send(bot, message.chat.id, "thinking")

    file = await bot.get_file(photo.file_id)
    buf = BytesIO()
    if file.file_path is None:
        return
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
    if message.from_user is None:
        return
    user_id = message.from_user.id
    if await _is_busy(user_id, message, language):
        return

    if message.voice is None:
        return
    voice = message.voice
    if voice.duration and voice.duration > settings.max_voice_duration_sec:
        await _reply(message, t("voice_too_long", language).format(settings.max_voice_duration_sec // 60))
        return
    if voice.file_size and voice.file_size > settings.max_upload_mb * 1024 * 1024:
        await _reply(message, t("file_too_large", language).format(settings.max_upload_mb))
        return

    await monkey.send(bot, message.chat.id, "thinking")

    file = await bot.get_file(voice.file_id)
    buf = BytesIO()
    if file.file_path is None:
        return
    await bot.download_file(file.file_path, buf)
    buf.name = "voice.oga"
    buf.seek(0)

    try:
        transcribed, _ = await api.transcribe_audio(buf, user_id=user_id, lang=language)
    except Exception as exc:
        logger.error("Voice transcription failed for user %d: %s", user_id, exc, exc_info=True)
        await monkey.send(bot, message.chat.id, "error")
        await _reply(message, t("voice_recognition_failed", language))
        return

    if not transcribed:
        await monkey.send(bot, message.chat.id, "error")
        await _reply(message, t("voice_recognition_failed", language))
        return

    await _run_handle(message, bot, language, user_id, transcribed)


@router.message(
    F.document | F.video | F.audio | F.sticker | F.animation,
    StateFilter("*"),
)
async def msg_unsupported(message: Message, language: str, bot: Bot) -> None:
    if not await _is_bot_mentioned(message, bot):
        return
    await _reply(message, t("unsupported_media", language))


@router.edited_message(F.text | F.photo, StateFilter("*"))
async def msg_edited(message: Message, language: str) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await _reply(message, t("edited_message_unsupported", language))
