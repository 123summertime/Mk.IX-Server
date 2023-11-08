from enum import Enum

from utils.dbCRUD import DB_CRUD, transaction

from fastapi.security import OAuth2PasswordBearer


class Database(Enum):
    DB = "UserInfo"
    ACC = "Account"
    GRP = "Group"
    REF = "OfflineRef"
    STO = "OfflineStorage"


class Collection(Enum):
    COLL_ACC = DB_CRUD(Database.DB.value, Database.ACC.value)
    COLL_GRP = DB_CRUD(Database.DB.value, Database.GRP.value)
    COLL_REF = DB_CRUD(Database.DB.value, Database.REF.value)
    COLL_STO = DB_CRUD(Database.DB.value, Database.STO.value)
<<<<<<< HEAD
    COLL_REQ = DB_CRUD(Database.DB.value, Database.REQ.value)
    TRANSACTION = transaction
=======
>>>>>>> parent of 80c3f56 (fix makegroup issue)


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = "hw4jf6uz8o4na1rc3pf9yxr8fn3gft3m"
    ACCESS_TOKEN_EXPIRE_MINUTES = 2160
    OAUTH2 = OAuth2PasswordBearer(tokenUrl="token")