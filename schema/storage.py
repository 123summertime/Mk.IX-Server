from pydantic import BaseModel


class StorageSchema(BaseModel):
    refTimes: int
    time: str
    type: str
    senderID: str   # user uuid
    senderKey: str  # user lastUpdate
    payload: str
