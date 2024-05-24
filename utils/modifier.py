import json

from utils.crud import FS
from schema.message import GetMessageSchema
from public.stateCode import CheckerState
from datetime import datetime, timezone


def forwardFileMessageModifier(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload
    file = FS.query(hashcode)
    if not file:
        return CheckerState.NOT_EXIST

    FS.update(hashcode, {"uploadDate": datetime.now(timezone.utc)})

    message.type = "file"
    message.payload = json.dumps({
            "name": file.name,
            "size": len(file.file),
            "hashcode": hashcode,
        })

    return CheckerState.OK


def beforeSendModify(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行原地修改
    '''
    callFunction = {
        "forwardFile": forwardFileMessageModifier,
    }

    if message.type not in callFunction:
        return message

    res = callFunction[message.type](userID, groupID, message)
    return res
