from pydantic import BaseModel


class DialogMessagesSet(BaseModel):
    messages: list
