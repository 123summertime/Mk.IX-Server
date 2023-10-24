from pydantic import BaseModel

class MessageSchema(BaseModel):
    time: str
    type: str
    sender: str
    payload: str
