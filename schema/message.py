from typing import Literal, Optional, Union

from pydantic import BaseModel

from public import RequestState


class BroadcastMeta(BaseModel):
    operation: str
    var: Optional[dict] = None


class MessagePayload(BaseModel):
    name: Optional[str] = None
    size: Optional[int] = None
    content: str
    meta: Optional[Union[dict, BroadcastMeta]] = dict()


class GetMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    groupType: Literal['group', 'friend']
    senderID: str = ""   # user集合中的uuid
    echo: Optional[Union[str, int]] = None
    payload: MessagePayload


class BroadcastMessageSchema(GetMessageSchema):
    pass


class SendMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    isSystemMessage: bool = False
    senderID: str = ""     # user集合中的uuid
    senderKey: str = ""    # user集合中的lastUpdate
    payload: MessagePayload


class SysMessageSchema(BaseModel):
    time: str = ""
    type: str
    subType: str | None = None
    target: str = ""
    targetKey: str = ""
    isSystemMessage: bool = True
    state: str = RequestState.NIL.value
    senderID: str = ""
    senderKey: str = ""
    payload: str
