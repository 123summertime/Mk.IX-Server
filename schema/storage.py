from typing import Any, Dict, Optional

from pydantic import BaseModel

from public import RequestState, SystemMessageType
from .message import MessagePayload, BroadcastMeta


class StorageSchema(BaseModel):
    time: str = ""
    type: str = ""
    senderID: str = ""   # user uuid
    payload: MessagePayload | None = None


class FileStorageSchema(BaseModel):
    name: str
    type: str
    group: Dict[str, int] = dict()
    file: Any   # GridOut


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


class NotificationMsgSchema(BaseModel):
    time: str
    type: str = SystemMessageType.NOTICE.value
    subType: str
    isSystemMessage: bool = True
    isGroupMessage: bool
    target: str         # 发送给target
    blank: str = ""     # 用来填充payload中的{}
    payload: str
    meta: Optional[BroadcastMeta] = None
