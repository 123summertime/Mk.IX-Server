import base64
import io

from fastapi import HTTPException, UploadFile, File, Form
from pydub import AudioSegment

from public.const import Limits
from schema.file import FileInput


# 验证用户的输入是否符合限制
class InputValidate:
    @staticmethod
    def validateStringLength(s: str, limit: Limits, name: str) -> str:
        limit = limit.value
        if not (limit['MIN'] <= len(s) <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"{name}的长度必须在{limit['MIN']}至{limit['MAX']}之间")
        return s

    @staticmethod
    def validateImageSize(image: str, limit: Limits, name: str) -> str:
        limit = limit.value
        # 初步判定大小 1KB文件编码后约为1400字符
        if len(image) > limit['MAX'] * 1400:
            raise HTTPException(status_code=400, detail=f"{name}图片大小必须在{limit['MIN']}KB至{limit['MAX']}]KB之间")
        try:
            imageDecode = base64.b64decode(image.split(',')[1])
        except Exception:
            raise HTTPException(status_code=400, detail="图片损坏")
        if not (limit['MIN'] <= len(imageDecode) // 1024 <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"{name}图片大小必须在{limit['MIN']}KB至{limit['MAX']}]KB之间")
        return image

    @staticmethod
    async def fileValidator(file: UploadFile) -> FileInput:
        limit = Limits.GROUP_FILE_SIZE_RANGE.value
        content = await file.read()
        size = len(content) // 1024
        if not (limit['MIN'] <= size <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"文件大小必须在{limit['MIN']}KB至{limit['MAX']}KB之间")
        return FileInput(fileName=file.filename, fileType=file.content_type, content=content)

    @staticmethod
    async def audioValidator(file: UploadFile) -> FileInput:
        limit = Limits.GROUP_AUDIO_LENGTH_RANGE.value
        content = await file.read()
        audio = AudioSegment.from_file(io.BytesIO(content))
        length = round(len(audio) / 1000)
        if not (limit['MIN'] <= length <= limit['MAX']):
            raise HTTPException(status_code=400, detail=f"语音时长必须在{limit['MIN']}s至{limit['MAX']}s之间")
        return FileInput(fileName=file.filename, fileType=file.content_type, content=content)

    @staticmethod
    async def validateInputFile(file: UploadFile = File(...),
                                fileType: str = Form(...)) -> FileInput:
        if fileType not in Limits.FILETYPE.value:
            raise HTTPException(status_code=400, detail=f"不允许上传的类型: {fileType}")

        mapping = {
            "file": InputValidate.fileValidator,
            "audio": InputValidate.audioValidator,
        }
        return await mapping[fileType](file)
