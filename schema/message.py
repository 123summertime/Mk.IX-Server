from pydantic import BaseModel


class MessageSchema(BaseModel):
    time: str
    type: str
    group: str
    sender: str
    payload: str


class OfflineMessageSchema(BaseModel):
    uuid: str
    group: str
    refTo: str
