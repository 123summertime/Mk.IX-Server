from typing import List, Any
from pydantic import BaseModel


class UserSchema(BaseModel):
    uuid: str
    userName: str
    password: str
    avatar: str
    lastUpdate: str     # 上次更新时间 只有在userName或avatar改变时才会更新
    groups: List[Any]   # 元素: 群objectID
