from public.const import Database
from schema.storage import StorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP
from schema.message import GetMessageSchema
from public.stateCode import CheckerState


def revokeMessageChecker(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
    getMessage = DB.query(
        {"time": message.payload},
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


def beforeSendCheck(userID: str, groupID: str, message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行检查
    '''
    callFunction = {
        "revoke": revokeMessageChecker,
    }

    if message.type not in callFunction:
        return CheckerState.OK

    res = callFunction[message.type](userID, groupID, message)
    return res
