import hashlib
from datetime import datetime

from const import Database, Collection
from utils.dbCRUD import DB_CRUD


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def timestamp():
    return ("{:.6f}".format(datetime.now().timestamp())).replace(".", "")


def beforeSendCheck(userID, groupID, message):
    if message.type == "revoke":
        DB = DB_CRUD(Database.StorageDB.value, groupID)
        getMessage = DB.query(
            {"time": message.payload},
            {"senderID": 1}
        )

        if not getMessage:
            return False

        userObjID = Collection.COLL_ACC.value.query(
            {"uuid": userID},
            {"_id": 1}
        )["_id"]

        targetObjID = Collection.COLL_ACC.value.query(
            {"uuid": getMessage["senderID"]},
            {"_id": 1}
        )["_id"]

        targetGroup = Collection.COLL_GRP.value.query(
            {"group": groupID},
            {"owner": 1, "admin": 1}
        )

        if not userID or not targetGroup:
            return False

        isOwner = userObjID == targetGroup["owner"]
        isAdmin = userObjID in targetGroup["admin"]

        if userObjID == targetObjID or isOwner or (isAdmin and targetObjID != targetGroup["owner"]):
            return True
        return False

    return True
