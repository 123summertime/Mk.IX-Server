from pydantic import BaseModel

from schema.message import MessagePayload
from public.stateCode import RequestState


class StorageSchema(BaseModel):
    time: str = ""
    type: str = ""
    senderID: str = ""   # user uuid
    senderKey: str = ""  # user lastUpdate
    payload: MessagePayload | None = None


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
