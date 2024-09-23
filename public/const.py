from enum import Enum

import pymongo
import yaml
from fastapi.security import OAuth2PasswordBearer

with open('config.yaml', 'r', encoding='utf-8') as F:
    config = yaml.safe_load(F)

database = config['Database']
auth = config['Auth']
default = config['Default']
limits = config['Limits']


class API(Enum):
    VERSION = "v1"


class Database(Enum):
    CLIENT = pymongo.MongoClient(database['HOST'], database['PORT'], maxPoolSize=database['MAX_POOL_SIZE'])
    INFO_DB = "UserInfo"
    ACCOUNT_COLLECTION = "Account"
    GROUP_COLLECTION = "Group"
    FILE_DB = "File"
    STORAGE_DB = "Storage"
    REQUEST_DB = "Request"
    FRIEND_REQUEST_COLLECTION = "Friend"


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = auth['SECRET_KEY']
    SALT = auth['SALT']
    USER_ACCESS_TOKEN_EXPIRE_MINUTES = auth['USER_ACCESS_TOKEN_EXPIRE_MINUTES']
    BOT_ACCESS_TOKEN_EXPIRE_MINUTES = auth['BOT_ACCESS_TOKEN_EXPIRE_MINUTES']
    OAUTH2 = OAuth2PasswordBearer(tokenUrl=f"/{API.VERSION.value}/user/token")


class Default(Enum):
    DEFAULT_AVATAR = default['DEFAULT_AVATAR']
    DEFAULT_BIO = default['DEFAULT_BIO']


class Limits(Enum):
    AVATAR_SIZE_RANGE = limits['AVATAR_SIZE_RANGE']
    REASON_LENGTH_RANGE = limits['REASON_LENGTH_RANGE']
    USER_NAME_LENGTH_RANGE = limits['USER_NAME_LENGTH_RANGE']
    USER_PASSWORD_LENGTH_RANGE = limits['USER_PASSWORD_LENGTH_RANGE']
    GROUP_NAME_LENGTH_RANGE = limits['GROUP_NAME_LENGTH_RANGE']
    GROUP_QA_LENGTH_RANGE = limits['GROUP_QA_LENGTH_RANGE']
    GROUP_AUDIO_LENGTH_RANGE = limits['GROUP_AUDIO_LENGTH_RANGE']
    GROUP_FILE_SIZE_RANGE = limits['GROUP_FILE_SIZE_RANGE']
    REQUEST_EXPIRE_MINUTES = limits['REQUEST_EXPIRE_MINUTES']
    MAX_DEVICE = limits['MAX_DEVICE']
    MAX_ONLINE_DEVICE = limits['MAX_ONLINE_DEVICE']

    TIME_LENGTH_RANGE = {"MIN": 13, "MAX": 13}  # 时间戳必须是13位
