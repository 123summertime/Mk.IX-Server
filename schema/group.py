from typing import List, Dict, Any
from pydantic import BaseModel


class GroupSchema(BaseModel):
    group: str
    name: str
    avatar: str
    lastUpdate: str     # 上次更新时间 只有在name或avatar改变时才会更新 用于前端缓存标识
    owner: Any          # 群主objectID
    admin: List[Any] = []    # 元素:管理员objectID
    user: List[Any] = []     # 元素:用户objectID
    question: Dict[str, str] = {} # {Q: A}
