from typing import List

from pydantic import BaseModel

from public.stateCode import RequestState
from schema.message import MessagePayload


class StorageSchema(BaseModel):
    time: str = ""
    type: str = ""
    senderID: str = ""   # user uuid
    payload: MessagePayload | None = None


class FileStorageSchema(BaseModel):
    name: str
    type: str
    group: List[str] = []
    file: bytes


class RequestMsgSchema(BaseModel):
    time: str = ""
    type: str = ""
    target: str = ""
    state: str = RequestState.PENDING.value
    senderID: str = ""
    payload: str = ""


class WebsocketTokenSchema(BaseModel):
    time: str
    uuid: str
    token: str
    device: str
