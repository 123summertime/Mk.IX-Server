from fastapi import HTTPException, Path

from schema.storage import FileStorageSchema
from utils.crud import FS


class OutputValidate:
    @staticmethod
    def validateFileExists(group: str = Path(...), hashcode: str = Path(...)) -> FileStorageSchema:
        file = FS.query(hashcode)
        if not file:
            raise HTTPException(status_code=400, detail=f"文件不存在或已过期")
        if group not in file.group:
            raise HTTPException(status_code=400, detail=f"文件不属于该群")

        return file
