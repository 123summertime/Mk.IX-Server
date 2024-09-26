from typing import Any

from pydantic import BaseModel

# 处理用户文件的Model


class FileInput(BaseModel):
    fileName: str
    fileType: str
    content: Any
