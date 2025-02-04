from typing import Any

from pydantic import BaseModel, Field

from .user import UserSchema
from .storage import RequestMsgSchema


class GroupSchema(BaseModel):
    id: Any = Field(default=None, alias="_id") # 数据库中的_id
    group: str | None = None
    name: str | None = None
    avatar: str | None = None
    lastUpdate: str | None = None    # 上次更新时间 只有在name或avatar改变时才会更新
    owner: Any = None                # 群主objectID
    admin: list[Any] = []            # 元素:管理员objectID
    user: list[Any] = []             # 元素:用户objectID
    question: dict[str, str] = {}    # {Q: A}
    announcement: str = ""           # 群公告
    ban: dict[str, str] = {}         # 群禁言 {uuid: end_time}


class Info(BaseModel):
    groupInfo: GroupSchema | None = None
    userInfo: UserSchema | None = None
    targetInfo: UserSchema | None = None
    requestInfo: RequestMsgSchema | None = None

    def __or__(self, other):
        return Info(
            groupInfo=self.groupInfo or other.groupInfo,
            userInfo=self.userInfo or other.userInfo,
            targetInfo=self.targetInfo or other.targetInfo,
            requestInfo=self.requestInfo or other.requestInfo
        )