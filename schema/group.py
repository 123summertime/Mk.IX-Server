from typing import List, Dict
from pydantic import BaseModel


class GroupSchema(BaseModel):
    group: str
    name: str
    owner: str
    avatar: str
    question: Dict = {}
    admin: List = []
    user: List = []
