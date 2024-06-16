import io
import json
from math import ceil
from pydub import AudioSegment

from utils.crud import FS
from schema.message import GetMessageSchema, MessagePayload
from public.stateCode import CheckerState
from datetime import datetime, timezone


def forwardFileMessageModifier(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.EXPIRED

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
        return CheckerState.UNKNOWN

    try:
        audio = AudioSegment.from_file(io.BytesIO(file.file))
        message.payload.meta = {"length": ceil(len(audio) / 1000)}
        return CheckerState.OK
    except Exception as e:
        return CheckerState.UNKNOWN


def beforeSendModify(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
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
