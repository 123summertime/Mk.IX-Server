from pydantic import BaseModel


class StorageSchema(BaseModel):
    refTimes: int
    type: str
    payload: str
