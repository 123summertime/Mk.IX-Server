from enum import Enum


# 请求状态 0等待审核 1群主已同意 2群主已拒绝 3管理员已同意 4管理员已拒绝 5用户已同意 6用户已拒绝
class RequestState(Enum):
    PENDING = 0
    ACCEPTED_BY_OWNER = 1
    REJECTED_BY_OWNER = 2
    ACCEPTED_BY_ADMIN = 3
    REJECTED_BY_ADMIN = 4
    ACCEPTED_BY_USER = 5
    REJECTED_BY_USER = 6


# 权限等级 0任何人 1群员及以上 2管理员及以上 3仅群主
class PermissionLevel(Enum):
    NONE = 0
    USER = 1
    ADMIN = 2
    OWNER = 3
