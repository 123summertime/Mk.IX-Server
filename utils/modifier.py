import io
import json
from pydub import AudioSegment

from utils.crud import FS
from schema.message import SendMessageSchema
from schema.payload import FilePayload
from public.stateCode import CheckerState
from datetime import datetime, timezone


def forwardFileMessageModifier(userID: str, groupID: str, message: SendMessageSchema) -> CheckerState:
    hashcode = message.payload
    file = FS.query(hashcode)
    if not file:
        return CheckerState.EXPIRED

    FS.update(hashcode, {"uploadDate": datetime.now(timezone.utc)})

    message.type = "file"
    message.payload = json.dumps({
            "name": file.name,
            "size": len(file.file),
            "hashcode": hashcode,
        })

    return CheckerState.OK


def audioFileMessageModifier(userID: str, groupID: str, message: SendMessageSchema) -> CheckerState:
    payload = FilePayload.parse_obj(json.loads(message.payload))
    hashcode = payload.hashcode
    file = FS.query(hashcode)
    if not file:
        return CheckerState.UNKNOWN

    try:
        audio = AudioSegment.from_file(io.BytesIO(file.file))
        payload.meta = {"length": round(len(audio) / 1000)}
        message.payload = json.dumps(dict(payload))
        return CheckerState.OK
    except Exception as e:
        return CheckerState.UNKNOWN


def beforeSendModify(userID: str, groupID: str, message: SendMessageSchema) -> CheckerState:
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
