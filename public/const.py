from enum import Enum

import pymongo
import yaml
from fastapi.security import OAuth2PasswordBearer

with open('config.yaml', 'r') as F:
    config = yaml.safe_load(F)


class API(Enum):
    VERSION = "v1"


class Database(Enum):
    CLIENT = pymongo.MongoClient(config['Database']['HOST'], config['Database']['PORT'], maxPoolSize=config['Database']['MAX_POOL_SIZE'])
    USER_DB = "UserInfo"
    STORAGE_DB = "Storage"
    REQUEST_DB = "Request"


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = config['Auth']['SECRET_KEY']
    USER_ACCESS_TOKEN_EXPIRE_MINUTES = config['Auth']['USER_ACCESS_TOKEN_EXPIRE_MINUTES']
    BOT_ACCESS_TOKEN_EXPIRE_MINUTES = config['Auth']['BOT_ACCESS_TOKEN_EXPIRE_MINUTES']
    OAUTH2 = OAuth2PasswordBearer(tokenUrl=f"/{API.VERSION.value}/user/token")


class Default(Enum):
    DEFAULT_AVATAR = config['Default']['DEFAULT_AVATAR']


class Limits(Enum):
    GROUP_NAME_LENGTH_RANGE = config['Limits']['GROUP_NAME_LENGTH_RANGE']
    GROUP_QA_LENGTH_RANGE = config['Limits']['GROUP_QA_LENGTH_RANGE']
    GROUP_AUDIO_LENGTH_RANGE = config['Limits']['GROUP_AUDIO_LENGTH_RANGE']
    GROUP_AVATAR_SIZE_RANGE = config['Limits']['GROUP_AVATAR_SIZE_RANGE']
    GROUP_FILE_SIZE_RANGE = config['Limits']['GROUP_FILE_SIZE_RANGE']
    GROUP_REQUEST_EXPIRE_MINUTES = config['Limits']['GROUP_REQUEST_EXPIRE_MINUTES']
    GROUP_INVITE_EXPIRE_MINUTES = config['Limits']['GROUP_INVITE_EXPIRE_MINUTES']



