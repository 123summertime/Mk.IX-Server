from typing import Any
from pydantic import BaseModel


class GetMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    senderID: str   # user集合中的uuid
    payload: str


class SendMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    senderID: str   # user集合中的uuid
    senderKey: str  # user集合中的lastUpdate
    payload: str


class OfflineMessageSchema(BaseModel):
    uuid: str
    group: str
    refTo: Any  # storage集合中的objectID
