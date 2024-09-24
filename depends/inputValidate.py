import base64

from fastapi import HTTPException

from public.const import Limits


# 验证用户的输入是否符合限制
class InputValidate:
    @staticmethod
    def validateStringLength(s: str, limit: Limits, name: str):
        limit = limit.value
        if not (limit['MIN'] <= len(s) <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"{name}的长度必须在{limit['MIN']}至{limit['MAX']}之间")
        return s

    @staticmethod
    def validateImageSize(image: str, limit: Limits, name: str):
        limit = limit.value
        # 初步判定大小 1KB文件编码后约为1400字符
        if len(image) > limit['MAX'] * 1400:
            raise HTTPException(status_code=400, detail=f"图片大小必须在{limit['MIN']}KB至{limit['MAX']}]KB之间")
        try:
            imageDecode = base64.b64decode(image.split(',')[1])
        except Exception:
            raise HTTPException(status_code=400, detail="图片损坏")
        if not (limit['MIN'] <= len(imageDecode) // 1024 <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"图片大小必须在{limit['MIN']}KB至{limit['MAX']}]KB之间")
        return image

    @staticmethod
    def validateFileSize():
        ...

    @staticmethod
    def validateAudioLength():
        ...
