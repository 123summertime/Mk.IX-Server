import base64

from public.const import Database, Limits
from public.stateCode import CheckerState
from schema.message import GetMessageSchema, BroadcastMessageSchema
from schema.storage import StorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP


def textMessageChecker(userID: str,
                       groupID: str,
                       message: GetMessageSchema) -> CheckerState:
    limit = Limits.GROUP_TEXT_LENGTH_RANGE.value
    MAX = limit['MAX']
    if message.payload.meta.get("encrypt", False):
        MAX += 32  # 加密后字符串可能稍长
    if not limit['MIN'] <= len(message.payload.content) <= MAX:
        return CheckerState.LIMIT_EXCEED
    return CheckerState.OK


def imageMessageChecker(userID: str,
                        groupID: str,
                        message: GetMessageSchema) -> CheckerState:
    limit = Limits.GROUP_IMAGE_SIZE_RANGE.value
    # 初步判定大小 1KB文件编码后约为1400字符
    if len(message.payload.content) > limit['MAX'] * 1400:
        return CheckerState.LIMIT_EXCEED
    if message.payload.meta.get("encrypt", False):
        return CheckerState.OK
    try:
        imageDecode = base64.b64decode(message.payload.content.split(',')[1])
    except Exception as e:
        return CheckerState.UNKNOWN
    if not (limit['MIN'] <= len(imageDecode) // 1024 <= limit['MAX']):
        return CheckerState.LIMIT_EXCEED
    return CheckerState.OK


def revokeMessageChecker(userID: str,
                         groupID: str,
                         message: GetMessageSchema) -> CheckerState:
    DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
    getMessage = DB.query(
        {"time": message.payload.content},
        {"senderID": 1}
    )

    if not getMessage:
        return CheckerState.NOT_EXIST

    # 获取自己的信息/被撤回用户的信息/该群的信息
    userObjID = ACCOUNT.query(
        {"uuid": userID},
        {"_id": 1}
    )
    targetObjID = ACCOUNT.query(
        {"uuid": getMessage.senderID},
        {"_id": 1}
    )
    targetGroup = GROUP.query(
        {"group": groupID},
        {"owner": 1, "admin": 1}
    )

    if not userObjID or not userObjID or not targetGroup:
        return CheckerState.NOT_EXIST

    isOwner = userObjID.id == targetGroup.owner
    isAdmin = userObjID.id in targetGroup.admin

    # 1.可以撤回自己的消息 2.群主可以撤回任何人消息 3.管理可以撤回除群主以外的消息
    if userObjID.id == targetObjID.id or isOwner or (isAdmin and targetObjID.id != targetGroup.owner):
        return CheckerState.OK
    return CheckerState.NO_PERMISSION


def beforeSendingCheck(userID: str,
                       groupID: str,
                       message: GetMessageSchema | BroadcastMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行检查
    '''
    if not (isinstance(message, BroadcastMessageSchema) or message.type in Limits.MESSAGE_TYPE.value):
        return CheckerState.NOT_ALLOWED_TYPE

    callFunction = {
        "text": textMessageChecker,
        "image": imageMessageChecker,
        "revokeRequest": revokeMessageChecker,
        # 对audio和file的检查已在depends/inputValidate.py里验证过 这里仅检查通过ws传入的信息
    }

    if message.type not in callFunction:
        return CheckerState.OK

    return callFunction[message.type](userID, groupID, message)
