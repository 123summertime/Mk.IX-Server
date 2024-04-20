from pydantic import BaseModel

from stateCode import RequestState


class StorageSchema(BaseModel):
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str


class RequestMsgSchema(BaseModel):
    time: str = ""
    type: str = ""
    group: str = ""
    groupKey: str = ""
    state: int = RequestState.PENDING.value
    senderID: str = ""
    senderKey: str = ""
    payload: str = ""
