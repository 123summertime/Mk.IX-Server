from typing import Any
from pydantic import BaseModel

from const import RequestState


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


class SysMessageSchema(BaseModel):
    time: str
    type: str
    group: str = ""
    groupKey: str = ""
    state: int = RequestState.PENDING.value
    senderID: str = ""
    senderKey: str = ""
    payload: str

