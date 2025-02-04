import hashlib
from datetime import datetime, timedelta

from jose import jwt

from public import API, Auth, Database, Limits
from schema.user import UserSchema
from .crud import FS


def hashPassword(password: str) -> str:
    withSalt = password + Auth.SALT.value
    return hashlib.sha256(withSalt.encode()).hexdigest()


def timestamp() -> str:
    '''
    以字符串的形式返回当前的时间戳，单位ms
    '''
    return ("{:.3f}".format(datetime.now().timestamp())).replace(".", "")


def createAccessToken(uuid, isBot) -> str:
    encode = {"uuid": uuid, "isBot": isBot}

    if isBot:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.BOT_ACCESS_TOKEN_EXPIRE_MINUTES.value)
    else:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.USER_ACCESS_TOKEN_EXPIRE_MINUTES.value)

    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token


def getVirtualGroupID(user1: UserSchema | str, user2: UserSchema | str) -> str:
    '''
    user1和user2是好友，虚拟群号通过以下方式计算
    '''
    if isinstance(user1, UserSchema):
        user1 = user1.uuid
    if isinstance(user2, UserSchema):
        user2 = user2.uuid
    return str(int(user1) * int(user2))


def getTargetFromVirtualGroupID(groupID: str, user: UserSchema | str):
    '''
    getVirtualGroupID的逆运算
    '''
    if isinstance(user, UserSchema):
        user = user.uuid
    return str(int(groupID) // int(user))


def cleaner():
    client = Database.CLIENT.value

    def execute(DBName, limit):
        DB = client[DBName.value]
        threshold = str(int(timestamp()) - limit.value * 60 * 1000)
        for name in DB.list_collection_names():
            collection = DB[name]
            result = collection.delete_many({"time": {"$lt": threshold}})
            if result.deleted_count:
                API.LOGGER.value.info(f"定时清理: 数据库 {DBName}: 集合{name}: 删除了 {result.deleted_count} 条文档")

    # 清理过期信息，群验证，好友请求，通知
    execute(Database.STORAGE_DB, Limits.MESSAGE_EXPIRE_MINUTES)
    execute(Database.REQUEST_DB, Limits.REQUEST_EXPIRE_MINUTES)
    execute(Database.NotificationDB, Limits.NOTIFICATION_EXPIRE_MINUTES)

    # 清理过期文件
    delCount = 0
    threshold = datetime.utcnow() - timedelta(minutes=Limits.MESSAGE_EXPIRE_MINUTES.value)
    files = client[Database.FILE_DB.value]["fs.files"].find({"uploadDate": {"$lt": threshold}})
    for file in files:
        FS.deleteByID(file["_id"])
        delCount += 1
    if delCount:
        API.LOGGER.value.info(f"定时清理: 删除了 {delCount} 个文件")


def checkerServerConfig():
    if Auth.SALT.value == "jSJ1oGX6siEa50Nmq6xlYvD0IfnUlKrj":
        API.LOGGER.value.warn("SALT使用默认值，可能会带来安全性问题。请修改config.yaml中的Auth.SALT")
    if Auth.SECRET_KEY.value == "hw4jf6uz8o4na1rc3pf9yxr8fn3gft3m":
        API.LOGGER.value.warn("SECRET_KEY使用默认值，可能会带来安全性问题。请修改config.yaml中的Auth.SECRET_KEY")


def createIndex():
    client = Database.CLIENT.value
    client[Database.INFO_DB.value][Database.ACCOUNT_COLLECTION.value].create_index([('uuid', 1)], unique=True)
    client[Database.INFO_DB.value][Database.GROUP_COLLECTION.value].create_index([('group', 1)], unique=True)
    client[Database.TOKEN_DB.value][Database.WEBSOCKET_TOKEN_COLLECTION.value].create_index([('time', 1)], unique=True)
    client[Database.REQUEST_DB.value][Database.FRIEND_REQUEST_COLLECTION.value].create_index([('time', 1)], unique=True)
    client[Database.REQUEST_DB.value][Database.GROUP_REQUEST_COLLECTION.value].create_index([('time', 1)], unique=True)
