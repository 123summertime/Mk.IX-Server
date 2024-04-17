from pydantic import BaseModel

# User


class Register(BaseModel):
    userName: str
    password: str


# Group
class GroupID(BaseModel):
    group: str


class Avatar(BaseModel):
    avatar: str


class GroupQA(BaseModel):
    Q: str = ""
    A: str = ""


class GroupRegister(GroupQA):
    name: str

