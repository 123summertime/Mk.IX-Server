from typing import List
from pydantic import BaseModel

class RegisterSchema(BaseModel):
    uuid: str
    userName: str
    password: str
    avatar: str
    groups: List = []