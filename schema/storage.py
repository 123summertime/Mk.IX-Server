from pydantic import BaseModel


class StorageSchema(BaseModel):
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str


class RequestMsgSchema(BaseModel):
    time: str
    type: str
    senderID: str
    senderKey: str
    payload: str
