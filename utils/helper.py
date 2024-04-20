import hashlib
from datetime import datetime

from schema.user import UserSchema
from schema.storage import StorageSchema

from const import Database, Collection
from utils.dbCRUD import DB_CRUD


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def timestamp():
    return ("{:.6f}".format(datetime.now().timestamp())).replace(".", "")


def convertObjectIDtoInfo(objID) -> UserSchema:
    info = Collection.ACCOUNT.value.query(
        {"_id": objID},
        {"_id": 0, "uuid": 1, "lastUpdate": 1}
    )
    return info


def beforeSendCheck(userID, groupID, message):
    if message.group != groupID:
        return "Failed"

    if message.type == "revoke":
        DB = DB_CRUD(Database.StorageDB.value, groupID, StorageSchema)
        getMessage = DB.query(
            {"time": message.payload},
            {"senderID": 1}
        )

        if not getMessage:
            return "Message is expired"

        userObjID = Collection.ACCOUNT.value.query(
            {"uuid": userID},
            {"_id": 1}
        ).id

        targetObjID = Collection.ACCOUNT.value.query(
            {"uuid": getMessage.senderID},
            {"_id": 1}
        ).id

        targetGroup = Collection.GROUP.value.query(
            {"group": groupID},
            {"owner": 1, "admin": 1}
        )

        if not userObjID or not targetGroup:
            return "Invalid user or group"

        isOwner = userObjID == targetGroup.owner
        isAdmin = userObjID in targetGroup.admin

        if userObjID == targetObjID or isOwner or (isAdmin and targetObjID != targetGroup.owner):
            return "OK"
        return "No permission"

    return "OK"
