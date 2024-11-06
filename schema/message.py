from pydantic import BaseModel, Field

from public.stateCode import RequestState, NotificationMsgSubtype


class MessagePayload(BaseModel):
    name: str | None = None
    size: int | None = None
    content: str
    meta: dict | None = dict()


class GetMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    senderID: str = ""   # user集合中的uuid
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
