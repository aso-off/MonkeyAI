from pydantic import BaseModel


class ChatCompleteRequest(BaseModel):
    user_id: int
    dialog_id: str | None = None
    message: str
    chat_mode: str = "assistant"
    model: str
    image_b64: str | None = None
    skip_moderation: bool = False
    is_premium: bool = False


class LimitCheckRequest(BaseModel):
    user_id: int
    kind: str = "msg"
    is_premium: bool = False


class Usage(BaseModel):
    """Канон OpenAI: точные значения из ответа API."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def of(cls, n_input: int, n_output: int) -> "Usage":
        return cls(input_tokens=n_input, output_tokens=n_output, total_tokens=n_input + n_output)


class ChatCompleteResponse(BaseModel):
    answer: str
    usage: Usage = Usage()
    n_first_removed: int
    is_flagged: bool
