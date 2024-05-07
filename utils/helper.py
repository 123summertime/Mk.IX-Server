import hashlib
from datetime import datetime, timedelta

from jose import jwt

from public.const import Database, Auth
from schema.storage import StorageSchema
from schema.user import UserSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def timestamp():
    return ("{:.3f}".format(datetime.now().timestamp())).replace(".", "")


def convertObjectIDtoInfo(objID) -> UserSchema:
    info = ACCOUNT.query(
        {"_id": objID},
        {"_id": 0, "uuid": 1, "lastUpdate": 1}
    )
    return info


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()

    if data["bot"]:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.BOT_ACCESS_TOKEN_EXPIRE_MINUTES.value)
    else:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.USER_ACCESS_TOKEN_EXPIRE_MINUTES.value)

    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)

    return token


def beforeSendCheck(userID, groupID, message):
    if message.group != groupID:
        return "Failed"

    if message.type == "revoke":
        DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
        getMessage = DB.query(
            {"time": message.payload},
            {"senderID": 1}
        )

        if not getMessage:
            return "Message is expired"

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
            return "Invalid user or group"

        isOwner = userObjID == targetGroup.owner
        isAdmin = userObjID in targetGroup.admin

        if userObjID == targetObjID or isOwner or (isAdmin and targetObjID != targetGroup.owner):
            return "OK"
        return "No permission"

    return "OK"
