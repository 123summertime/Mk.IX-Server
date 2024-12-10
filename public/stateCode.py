from enum import Enum


class RequestState(Enum):
    NIL = "无"
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
    LIMIT_EXCEED = "超出服务器限制"
    NOT_EXIST = "不存在或已过期"
    NO_PERMISSION = "没有权限"
    NOT_ALLOWED_TYPE = "不允许的类型"

    def __bool__(self):
        return self is CheckerState.OK


class SystemMessageType(Enum):
    ECHO = "echo"
    FAIL = "fail"
    BAN = "ban"
    LOGOUT = "logout"
    NOTICE = "notice"
    JOIN = "join"
    JOINED = "joined"
    FRIEND = "friend"
    FRIENDED = "friended"


class NotificationMsgSubtype(Enum):
    NIL = "Nil"
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"
