from typing import List, Dict, Any

from pydantic import BaseModel, Field


class GroupSchema(BaseModel):
    id: Any = Field(default=None, alias="_id") # 数据库中的_id
    group: str | None = None
    name: str | None = None
    avatar: str | None = None
    lastUpdate: str | None = None    # 上次更新时间 只有在name或avatar改变时才会更新 用于前端缓存标识
    owner: Any = None                # 群主objectID
    admin: List[Any] = []            # 元素:管理员objectID
    user: List[Any] = []             # 元素:用户objectID
    question: Dict[str, str] = {}    # {Q: A}
