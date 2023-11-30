from typing import List
from pydantic import BaseModel


class UserSchema(BaseModel):
    uuid: str
    userName: str
    password: str
    avatar: str
    lastUpdate: str     # 上次更新时间 只有在userName或avatar改变时才会更新 用于前端缓存标识
    groups: List   # 元素: 群objectID
