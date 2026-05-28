from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DialogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    chat_mode: str
    model: str
    start_time: datetime
    messages: list


class MessageAppend(BaseModel):
    user_message: str
    bot_message: str


class DialogMessagesSet(BaseModel):
    messages: list
