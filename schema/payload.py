from pydantic import BaseModel


class Avatar(BaseModel):
    avatar: str


class GroupQA(BaseModel):
    Q: str = ""
    A: str = ""

