from typing import List
from pydantic import BaseModel

class GroupSchema(BaseModel):
    group: str
    name: str
    owner: str
    admin: List = []
    user: List = []
