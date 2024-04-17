from enum import Enum

from utils.dbCRUD import DB_CRUD

from fastapi.security import OAuth2PasswordBearer


class API(Enum):
    version = "v1"


class Database(Enum):
    UserDB = "UserInfo"
    StorageDB = "Storage"
    ReqDB = "Requset"

    ACC = "Account"
    GRP = "Group"


class Collection(Enum):
    COLL_ACC = DB_CRUD(Database.UserDB.value, Database.ACC.value)
    COLL_GRP = DB_CRUD(Database.UserDB.value, Database.GRP.value)


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = "hw4jf6uz8o4na1rc3pf9yxr8fn3gft3m"
    ACCESS_TOKEN_EXPIRE_MINUTES = 2160
    OAUTH2 = OAuth2PasswordBearer(tokenUrl="/v1/user/token")


# 0等待审核 1群主已同意 2群主已拒绝 3管理员已同意 4管理员已拒绝 5用户已同意 6用户已拒绝
class RequestState(Enum):
    PENDING = 0
    ACCEPTED_BY_OWNER = 1
    REJECTED_BY_OWNER = 2
    ACCEPTED_BY_ADMIN = 3
    REJECTED_BY_ADMIN = 4
    ACCEPTED_BY_USER = 5
    REJECTED_BY_USER = 6


class Miscellaneous(Enum):
    # 默认用户/群头像 Base64格式
    DEFAULT_AVATAR = "data:image/png;base64,/9j/4AAQSkZJRgABAQEAkACQAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCAAwADADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDzeiiiugzCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//2Q=="
    GROUP_NAME_LENGTH_RANGE = [1, 16]
    GROUP_QA_LENGTH_RANGE = [0, 16]
    GROUP_AVATAR_SIZE_RANGE = [0, 1024] # KB
    GROUP_REQUEST_EXPIRE_MINUTES = 10080
    GROUP_INVITE_EXPIRE_MINUTES = 10080