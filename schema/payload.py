from pydantic import BaseModel

from schema.group import GroupSchema
from schema.user import UserSchema


# User
class Register(BaseModel):
    userName: str
    password: str


# Group
class Info(BaseModel):
    groupInfo: GroupSchema
    userInfo: UserSchema


class Note(BaseModel):
    note: str


class GroupQA(BaseModel):
    Q: str = ""
    A: str = ""


class GroupRegister(GroupQA):
    name: str


class FilePayload(BaseModel):
    name: str
    size: int
    hashcode: str
    meta: dict = {}
