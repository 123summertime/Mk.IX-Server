from pydantic import BaseModel

from public.stateCode import RequestState


class MessagePayload(BaseModel):
    name: str | None = None
    size: int | None = None
    content: str = ""
    meta: dict | None = None


class GetMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    senderID: str = ""   # user集合中的uuid
    payload: MessagePayload


class SendMessageSchema(BaseModel):
    time: str
    type: str
    group: str
    senderID: str = ""   # user集合中的uuid
    senderKey: str = ""  # user集合中的lastUpdate
    payload: MessagePayload


class SysMessageSchema(BaseModel):
    time: str = ""
    type: str = ""
    target: str = ""
    targetKey: str = ""
    state: str = RequestState.PENDING.value
    senderID: str = ""
    senderKey: str = ""
    payload: str = ""
