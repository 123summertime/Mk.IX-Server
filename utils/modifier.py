import io
from datetime import datetime, timezone

from pydub import AudioSegment

from public.stateCode import CheckerState
from schema.message import GetMessageSchema
from utils.crud import FS


def forwardFileMessageModifier(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.NOT_EXIST

    FS.update(hashcode, {"uploadDate": datetime.now(timezone.utc)})

    message.type = "file"
    message.payload.name = file.name
    message.payload.size = len(file.file)
    message.payload.content = hashcode

    return CheckerState.OK


def audioFileMessageModifier(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.NOT_EXIST

    # 将语音分为chunkCount段，获取每段的音量大小，放入meta字段中
    try:
        audio = AudioSegment.from_file(io.BytesIO(file.file))
        chunkCount = min(50, (len(audio) // 1000) + 2)
        chunkLength = len(audio) // chunkCount
        audioChunks = [audio[i: i + chunkLength].rms for i in range(0, len(audio), chunkLength)]
        maxVolume = max(audioChunks)
        volume = [v / maxVolume * 100 // 1 for v in audioChunks]
        message.payload.meta = {
            "length": round(len(audio) / 1000, 2),
            "volume": volume
        }
        return CheckerState.OK
    except Exception as e:
        return CheckerState.UNKNOWN


def beforeSendingModify(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行原地修改
    '''
    callFunction = {
        "audio": audioFileMessageModifier,
        "forwardFile": forwardFileMessageModifier,
    }

    if message.type not in callFunction:
        return CheckerState.OK

    res = callFunction[message.type](userID, groupID, message)
    return res
