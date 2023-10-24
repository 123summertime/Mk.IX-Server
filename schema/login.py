from typing import Dict
from pydantic import BaseModel

class RegisterSchema(BaseModel):
    uuid: str
    userName: str
    password: str
    avatar: str
    online: bool = False
    groups: Dict[str, None] = {}