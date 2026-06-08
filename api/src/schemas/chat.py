from pydantic import BaseModel


class ChatCompleteRequest(BaseModel):
    user_id: int
    dialog_id: str | None = None
    message: str
    dialog_messages: list = []
    chat_mode: str = "assistant"
    model: str
    image_b64: str | None = None
    skip_moderation: bool = False


class ChatCompleteResponse(BaseModel):
    answer: str
    n_input_tokens: int
    n_output_tokens: int
    n_first_removed: int
    is_flagged: bool
