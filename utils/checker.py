from public.const import Database, Limits
from public.stateCode import CheckerState
from schema.message import GetMessageSchema, BroadcastMessageSchema
from schema.storage import StorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP


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
                       message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行检查
    '''
    if not (isinstance(message, BroadcastMessageSchema) or message.type in Limits.MESSAGE_TYPE.value):
        return CheckerState.NOT_ALLOWED_TYPE

    callFunction = {
        "revoke": revokeMessageChecker,
    }

    if message.type not in callFunction:
        return CheckerState.OK

    return callFunction[message.type](userID, groupID, message)
