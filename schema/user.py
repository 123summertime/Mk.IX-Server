from typing import List, Any

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    id: Any = Field(default=None, alias="_id") # 数据库中的_id
    uuid: str | None = None
    userName: str | None = None
    password: str | None = None
    avatar: str | None = None
    bio: str | None = None
    lastSeen: str | None = None # dict[str, str] | None = None      # 上次下线时间
    lastUpdate: str | None = None    # 上次更新时间 只有在userName或avatar改变时才会更新
    groups: List[Any] = []    # 元素: 群objectID
