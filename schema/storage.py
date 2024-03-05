from pydantic import BaseModel


class StorageSchema(BaseModel):
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str
