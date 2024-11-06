from pydantic import BaseModel, validator

from depends.inputValidate import InputValidate
from public.const import Limits

# 处理用户简单数据类型的Model


class UserRegister(BaseModel):
    name: str
    password: str

    @validator('name')
    def validateName(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_NAME_LENGTH_RANGE, "昵称")

    @validator('password')
    def validatePassword(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_PASSWORD_LENGTH_RANGE, "密码")


class GroupA(BaseModel):
    A: str

    @validator('A')
    def validateA(cls, s):
        return InputValidate.validateStringLength(s, Limits.REASON_LENGTH_RANGE, "回答")


class GroupQA(GroupA):
    Q: str

    @validator('Q')
    def validateQ(cls, s):
        return InputValidate.validateStringLength(s, Limits.GROUP_QA_LENGTH_RANGE, "问题")


class GroupRegister(GroupQA):
    name: str

    @validator('name')
    def validateName(cls, s):
        return InputValidate.validateStringLength(s, Limits.GROUP_NAME_LENGTH_RANGE, "群名")


class GroupName(BaseModel):
    name: str

    @validator('name')
    def validateName(cls, s):
        return InputValidate.validateStringLength(s, Limits.GROUP_NAME_LENGTH_RANGE, "群名")


class GroupAvatar(BaseModel):
    avatar: str

    @validator('avatar')
    def validateAvatar(cls, s):
        return InputValidate.validateImageSize(s, Limits.AVATAR_SIZE_RANGE, "头像")


class Reason(BaseModel):
    reason: str

    @validator('reason')
    def validateReason(cls, s):
        return InputValidate.validateStringLength(s, Limits.REASON_LENGTH_RANGE, "申请理由")
