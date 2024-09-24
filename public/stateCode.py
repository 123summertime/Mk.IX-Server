from enum import Enum


# 请求状态
class RequestState(Enum):
    PENDING = "等待审核"
    ACCEPTED_BY_OWNER = "群主已同意"
    REJECTED_BY_OWNER = "群主已拒绝"
    ACCEPTED_BY_ADMIN = "管理员已同意"
    REJECTED_BY_ADMIN = "管理员已拒绝"
    ACCEPTED_BY_USER = "用户已同意"
    REJECTED_BY_USER = "用户已拒绝"
    ACCEPTED = "已同意"
    REJECTED = "已拒绝"


class CheckerState(Enum):
    OK = "OK"
    UNKNOWN = "未知错误"
    LIMIT_EXCEED = "时长/大小超出限制"
    NOT_EXIST = "不存在"
    NO_PERMISSION = "没有权限"

    def __bool__(self):
        return self is CheckerState.OK
