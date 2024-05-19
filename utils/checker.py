from public.const import Database
from schema.storage import StorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP


def beforeSendCheck(userID, groupID, message):
    if message.group != groupID:
        return "未知错误"

    if message.type == "revoke":
        DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
        getMessage = DB.query(
            {"time": message.payload},
            {"senderID": 1}
        )

        if not getMessage:
            return "消息已过期/不存在"

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
            return "用户或群不存在"

        isOwner = userObjID == targetGroup.owner
        isAdmin = userObjID in targetGroup.admin

        if userObjID == targetObjID or isOwner or (isAdmin and targetObjID != targetGroup.owner):
            return "OK"
        return "没有权限"

    return "OK"
