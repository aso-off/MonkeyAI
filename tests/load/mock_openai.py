# Заглушка OpenAI для нагрузки. Запуск: uvicorn mock_openai:app --port 9090
# В config.yml: openai_api_base: http://127.0.0.1:9090/v1

import json
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="mock-openai")

_ANSWER = "Mock answer for load testing. " * 8
_USAGE = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}

_MODERATION_CATEGORIES = [
    "harassment", "harassment/threatening",
    "hate", "hate/threatening",
    "illicit", "illicit/violent",
    "self-harm", "self-harm/intent", "self-harm/instructions",
    "sexual", "sexual/minors",
    "violence", "violence/graphic",
]


def _chat_completion(model: str) -> dict:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _ANSWER},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": _USAGE,
    }


async def _responses_sse():
    seq = 0
    for word in _ANSWER.split():
        seq += 1
        event = {
            "type": "response.output_text.delta",
            "sequence_number": seq,
            "item_id": "msg_mock",
            "output_index": 0,
            "content_index": 0,
            "delta": word + " ",
            "logprobs": [],
        }
        yield f"event: response.output_text.delta\ndata: {json.dumps(event)}\n\n"


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = await request.json()
    return JSONResponse(_chat_completion(body.get("model", "mock")))


@app.post("/v1/responses")
@app.post("/responses")
async def responses(request: Request):
    body = await request.json()
    if body.get("stream"):
        return StreamingResponse(_responses_sse(), media_type="text/event-stream")
    return JSONResponse({
        "id": "resp_mock",
        "object": "response",
        "created_at": int(time.time()),
        "model": body.get("model", "mock"),
        "output_text": _ANSWER,
        "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    })


@app.post("/v1/moderations")
@app.post("/moderations")
async def moderations(request: Request) -> JSONResponse:
    return JSONResponse({
        "id": "modr-mock",
        "model": "omni-moderation-latest",
        "results": [
            {
                "flagged": False,
                "categories": {c: False for c in _MODERATION_CATEGORIES},
                "category_scores": {c: 0.0 for c in _MODERATION_CATEGORIES},
                "category_applied_input_types": {c: [] for c in _MODERATION_CATEGORIES},
            }
        ],
    })


@app.post("/v1/images/generations")
@app.post("/images/generations")
async def images(request: Request) -> JSONResponse:
    return JSONResponse({
        "created": int(time.time()),
        "data": [{"url": "http://127.0.0.1:9090/mock-image.png"}],
    })


@app.post("/v1/audio/transcriptions")
@app.post("/audio/transcriptions")
async def transcriptions(request: Request) -> JSONResponse:
    return JSONResponse({"text": "mock transcription"})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
