from pydantic import BaseModel


class StorageSchema(BaseModel):
    messageID: str
    refTimes: int
    time: str
    type: str
    sender: str
    payload: str
