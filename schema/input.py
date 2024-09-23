from pydantic import BaseModel, validator

from utils.validate import Validate
from public.const import Limits


# User
class UserRegister(BaseModel):
    name: str
    password: str

    @validator('name')
    def validateUserName(cls, s):
        return Validate.validateStringLength(s, Limits.USER_NAME_LENGTH_RANGE, "昵称")

    @validator('password')
    def validatePassword(cls, s):
        return Validate.validateStringLength(s, Limits.USER_PASSWORD_LENGTH_RANGE, "密码")


class GroupA(BaseModel):
    A: str

    @validator('A')
    def validateA(cls, s):
        return Validate.validateStringLength(s, Limits.REASON_LENGTH_RANGE, "回答")


class GroupQA(GroupA):
    Q: str

    @validator('Q')
    def validateQ(cls, s):
        return Validate.validateStringLength(s, Limits.GROUP_QA_LENGTH_RANGE, "问题")


class GroupRegister(GroupQA):
    name: str

    @validator('name')
    def validateName(cls, s):
        return Validate.validateStringLength(s, Limits.GROUP_NAME_LENGTH_RANGE, "群名")


class GroupName(BaseModel):
    name: str

    @validator('name')
    def validateName(cls, s):
        return Validate.validateStringLength(s, Limits.GROUP_NAME_LENGTH_RANGE, "群名")


class GroupAvatar(BaseModel):
    avatar: str

    @validator('avatar')
    def validateName(cls, s):
        return Validate.validateImageSize(s, Limits.AVATAR_SIZE_RANGE, "头像")


class Reason(BaseModel):
    reason: str

    @validator('reason')
    def validateName(cls, s):
        return Validate.validateStringLength(s, Limits.REASON_LENGTH_RANGE, "申请理由")


class Time(BaseModel):
    time: str

    @validator('time')
    def validateName(cls, s):
        return Validate.validateStringLength(s, Limits.TIME_LENGTH_RANGE, "时间")
