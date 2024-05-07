from pydantic import BaseModel

from public.stateCode import RequestState


class StorageSchema(BaseModel):
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str


class FileStorageSchema(BaseModel):
    name: str
    type: str
    file: bytes


class RequestMsgSchema(BaseModel):
    time: str = ""
    type: str = ""
    group: str = ""
    groupKey: str = ""
    state: int = RequestState.PENDING.value
    senderID: str = ""
    senderKey: str = ""
    payload: str = ""
