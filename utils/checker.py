import json

from public.const import Database, Limits
from schema.storage import StorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP
from schema.message import GetMessageSchema, MessagePayload
from public.stateCode import CheckerState
from pydub import AudioSegment


def revokeMessageChecker(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
    getMessage = DB.query(
        {"time": message.payload.content},
        {"senderID": 1}
    )

    if not getMessage:
        return CheckerState.EXPIRED

    userObjID = ACCOUNT.query(
        {"uuid": userID},
        {"_id": 1}
    ).id
    targetObjID = ACCOUNT.query(
        {"uuid": getMessage.senderID},
        {"_id": 1}
    ).id
    targetGroup = GROUP.query(
        {"group": groupID},
        {"owner": 1, "admin": 1}
    )

    if not userObjID or not targetGroup:
        return CheckerState.NOT_EXIST

    isOwner = userObjID == targetGroup.owner
    isAdmin = userObjID in targetGroup.admin

    if userObjID == targetObjID or isOwner or (isAdmin and targetObjID != targetGroup.owner):
        return CheckerState.OK
    return CheckerState.NO_PERMISSION


def audioMessageChecker(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.UNKNOWN

    try:
        minLength, maxLength = Limits.GROUP_AUDIO_LENGTH_RANGE
        audio = AudioSegment.from_file(io.BytesIO(file.file))
        length = round(len(audio) / 1000)
        if not (minLength <= length <= maxLength):
            return CheckerState.EXCEED_LIMIT
        return CheckerState.OK
    except Exception as e:
        return CheckerState.UNKNOWN


def beforeSendCheck(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行检查
    '''
    callFunction = {
        "audio": audioMessageChecker,
        "revoke": revokeMessageChecker,
    }

    if message.type not in callFunction:
        return CheckerState.OK

    res = callFunction[message.type](userID, groupID, message)
    return res
