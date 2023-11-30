from pydantic import BaseModel


class StorageSchema(BaseModel):
    refTimes: int
    time: str
    type: str
    senderID: str
    senderKey: str
    payload: str
