from pydantic import BaseModel

from const import RequestState


class StorageSchema(BaseModel):
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str


class RequestMsgSchema(BaseModel):
    time: str
    type: str
    group: str
    groupKey: str
    state: int = RequestState.WAITING.value
    senderID: str
    senderKey: str
    payload: str
