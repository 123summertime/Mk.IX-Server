from pydantic import BaseModel


class ModifyAvatar(BaseModel):
    avatar: str
