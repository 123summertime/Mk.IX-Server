from enum import Enum

from utils.dbCRUD import DB_CRUD

from fastapi.security import OAuth2PasswordBearer


class Database(Enum):
    DB = "UserInfo"
    ACC = "Account"
    GRP = "Group"
    REF = "OfflineRef"
    STO = "OfflineStorage"
    REQ = "Request"


class Collection(Enum):
    COLL_ACC = DB_CRUD(Database.DB.value, Database.ACC.value)
    COLL_GRP = DB_CRUD(Database.DB.value, Database.GRP.value)
    COLL_REF = DB_CRUD(Database.DB.value, Database.REF.value)
    COLL_STO = DB_CRUD(Database.DB.value, Database.STO.value)
    COLL_REQ = DB_CRUD(Database.DB.value, Database.REQ.value)


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = "hw4jf6uz8o4na1rc3pf9yxr8fn3gft3m"
    ACCESS_TOKEN_EXPIRE_MINUTES = 2160
    OAUTH2 = OAuth2PasswordBearer(tokenUrl="token")


class Miscellaneous(Enum):
    # 默认用户/群头像 Base64格式
    DEFAULT_AVATAR = "/9j/4AAQSkZJRgABAQEAkACQAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCAAwADADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDzeiiiugzCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//2Q=="
