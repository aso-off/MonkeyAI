import base64
import json
import logging
from io import BytesIO

from core.security import verify_service_token
from db.db import get_session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from schemas.chat import ChatCompleteRequest, ChatCompleteResponse, Usage
from services.messages import assistant_message, user_message
from services.moderation import moderate_content
from services.openai import ChatGPT
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_CONTEXT_LIMIT = 20


async def _resolve_dialog_id(session: AsyncSession, req: ChatCompleteRequest) -> str | None:
    if req.dialog_id:
        return req.dialog_id
    user = await user_repo.get_user(session, req.user_id)
    return user.state.current_dialog_id if user else None


async def _persist_chat_result(
    session: AsyncSession,
    req: ChatCompleteRequest,
    dialog_id: str | None,
    answer: str,
    n_input: int,
    n_output: int,
    image_buffer: BytesIO | None,
) -> None:
    if dialog_id is None:
        return
    b64: str | None = None
    if image_buffer:
        image_buffer.seek(0)
        b64 = base64.b64encode(image_buffer.read()).decode()
    content: str | list = (
        [{"type": "text", "text": req.message},
         {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
        if b64 else req.message
    )
    u_msg = user_message(content)
    a_msg = assistant_message(
        answer,
        parent_id=u_msg["id"],
        model=req.model,
        usage=Usage.of(n_input, n_output).model_dump(),
    )
    await dialog_repo.append_messages(session, req.user_id, dialog_id, [u_msg, a_msg])
    await dialog_repo.update_n_used_tokens(session, req.user_id, req.model, n_input, n_output)
    await user_repo.update_last_interaction(session, req.user_id)


async def _run_stream(req: ChatCompleteRequest, session: AsyncSession):
    """Async generator yielding SSE lines."""
    image_buffer: BytesIO | None = None
    if req.image_b64:
        try:
            image_buffer = BytesIO(base64.b64decode(req.image_b64))
        except Exception:
            payload = json.dumps({"status": "error", "text": "Invalid image data",
                                  "usage": Usage().model_dump(),
                                  "n_first_removed": 0, "is_flagged": False})
            yield f"data: {payload}\n\n"
            return
        image_buffer.name = "image.jpg"

    is_flagged, _cats, _scores = await moderate_content(text=req.message, image_buffer=image_buffer)
    if image_buffer is not None:
        image_buffer.seek(0)
    if is_flagged and not req.skip_moderation:
        payload = json.dumps({
            "status": "flagged",
            "text": "",
            "usage": Usage().model_dump(),
            "n_first_removed": 0,
            "is_flagged": True,
        })
        yield f"data: {payload}\n\n"
        return

    chatgpt = ChatGPT(model=req.model)

    # серверный контекст
    dialog_id = await _resolve_dialog_id(session, req)
    context: list = []
    if dialog_id:
        context = await dialog_repo.get_context(session, req.user_id, dialog_id, _CONTEXT_LIMIT)

    if image_buffer is not None:
        gen = chatgpt.send_vision_message_stream(
            req.message,
            dialog_messages=context,
            chat_mode=req.chat_mode,
            image_buffer=image_buffer,
        )
    else:
        gen = chatgpt.send_message_stream(
            req.message,
            dialog_messages=context,
            chat_mode=req.chat_mode,
        )

    n_input = n_output = n_removed = 0
    final_answer = ""
    reasoning = ""

    try:
        async for status, answer, reasoning, (n_input, n_output), n_removed in gen:
            final_answer = answer
            payload = json.dumps({
                "status": status,
                "text": answer,
                "reasoning": reasoning,
                "usage": Usage.of(n_input, n_output).model_dump(),
                "n_first_removed": n_removed,
                "is_flagged": False,
            })
            yield f"data: {payload}\n\n"
    except Exception:
        logger.exception("Stream generation failed for user %d", req.user_id)
        # чистый финальный кадр вместо обрыва chunked
        payload = json.dumps({
            "status": "finished",
            "text": final_answer,
            "reasoning": reasoning,
            "usage": Usage.of(n_input, n_output).model_dump(),
            "n_first_removed": n_removed,
            "is_flagged": False,
        })
        yield f"data: {payload}\n\n"

    # Persist to DB after full answer
    if final_answer:
        try:
            await _persist_chat_result(
                session, req, dialog_id, final_answer, n_input, n_output, image_buffer
            )
        except Exception:
            logger.exception("Failed to persist chat result for user %d", req.user_id)


@router.post("/complete")
async def chat_complete(
    req: ChatCompleteRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    """
    Non-streaming: returns full answer at once.
    Bot uses this when enable_message_streaming=False.
    """
    image_buffer: BytesIO | None = None
    if req.image_b64:
        try:
            image_buffer = BytesIO(base64.b64decode(req.image_b64))
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_base64") from None
        image_buffer.name = "image.jpg"

    is_flagged, _cats, _scores = await moderate_content(text=req.message, image_buffer=image_buffer)
    if image_buffer is not None:
        image_buffer.seek(0)
    if is_flagged and not req.skip_moderation:
        return ChatCompleteResponse(
            answer="", n_first_removed=0, is_flagged=True,
        )

    chatgpt = ChatGPT(model=req.model)

    # серверный контекст
    dialog_id = await _resolve_dialog_id(session, req)
    context: list = []
    if dialog_id:
        context = await dialog_repo.get_context(session, req.user_id, dialog_id, _CONTEXT_LIMIT)

    if image_buffer is not None:
        answer, (n_input, n_output), n_removed = await chatgpt.send_vision_message(
            req.message, dialog_messages=context,
            chat_mode=req.chat_mode, image_buffer=image_buffer,
        )
    else:
        answer, (n_input, n_output), n_removed = await chatgpt.send_message(
            req.message, dialog_messages=context, chat_mode=req.chat_mode,
        )

    try:
        await _persist_chat_result(session, req, dialog_id, answer, n_input, n_output, image_buffer)
    except Exception:
        logger.exception("Failed to persist chat result for user %d", req.user_id)

    return ChatCompleteResponse(
        answer=answer,
        usage=Usage.of(n_input, n_output),
        n_first_removed=n_removed,
        is_flagged=False,
    )


@router.post("/stream")
async def chat_stream(
    req: ChatCompleteRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    """SSE streaming: yields data: <json> lines until status=finished."""
    return StreamingResponse(
        _run_stream(req, session),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
