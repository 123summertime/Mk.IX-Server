from pydantic import BaseModel, validator

from public import Limits
from .inputValidate import InputValidate

# 处理用户简单数据类型的Model


class Username(BaseModel):
    name: str

    @validator('name')
    def validateName(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_NAME_LENGTH_RANGE, "昵称")


class Password(BaseModel):
    password: str

    @validator('password')
    def validatePassword(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_PASSWORD_LENGTH_RANGE, "密码")


class UserRegister(BaseModel):
    name: str
    password: str

    @validator('name')
    def validateName(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_NAME_LENGTH_RANGE, "昵称")

    @validator('password')
    def validatePassword(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_PASSWORD_LENGTH_RANGE, "密码")


class Bio(BaseModel):
    bio: str

    @validator('bio')
    def validateBio(cls, s):
        return InputValidate.validateStringLength(s, Limits.USER_BIO_LENGTH_RANGE, "简介")


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


class GroupAnnouncement(BaseModel):
    announcement: str

    @validator('announcement')
    def validateAnnouncement(cls, s):
        return InputValidate.validateStringLength(s, Limits.GROUP_ANN_LENGTH_RANGE, "群公告")


class Avatar(BaseModel):
    avatar: str

    @validator('avatar')
    def validateAvatar(cls, s):
        return InputValidate.validateImageSize(s, Limits.AVATAR_SIZE_RANGE, "头像")


class Reason(BaseModel):
    reason: str

    @validator('reason')
    def validateReason(cls, s):
        return InputValidate.validateStringLength(s, Limits.REASON_LENGTH_RANGE, "申请理由")
