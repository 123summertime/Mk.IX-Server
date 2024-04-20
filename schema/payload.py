from pydantic import BaseModel

from schema.user import UserSchema
from schema.group import GroupSchema


# User
class Register(BaseModel):
    userName: str
    password: str


# Group
class Info(BaseModel):
    groupInfo: GroupSchema
    userInfo: UserSchema


# class GroupID(BaseModel):
#     group: str
#
#
# class Name(BaseModel):
#     name: str
#
#
# class Avatar(BaseModel):
#     avatar: str


class Note(BaseModel):
    note: str


class GroupQA(BaseModel):
    Q: str = ""
    A: str = ""


class GroupRegister(GroupQA):
    name: str

