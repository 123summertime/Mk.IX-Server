from enum import Enum
import logging

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
    LOGGER = logging.getLogger('logger')


class Database(Enum):
    CLIENT = pymongo.MongoClient(database['HOST'], database['PORT'], maxPoolSize=database['MAX_POOL_SIZE'])

    # 用户数据 群数据
    INFO_DB = "UserInfo"
    ACCOUNT_COLLECTION = "Account"
    GROUP_COLLECTION = "Group"

    # 上传的文件
    FILE_DB = "File"

    # 群内消息 groupID作为集合名
    STORAGE_DB = "Storage"

    # 通知消息 userID作为集合名
    NotificationDB = "Notification"

    # 申请类型消息 申请入群及好友申请
    REQUEST_DB = "Request"
    GROUP_REQUEST_COLLECTION = "Group"
    FRIEND_REQUEST_COLLECTION = "Friend"

    # websocket连接凭证
    TOKEN_DB = "Token"
    WEBSOCKET_TOKEN_COLLECTION = "WSToken"


class Auth(Enum):
    ALGORITHM = "HS256"
    SECRET_KEY = auth['SECRET_KEY']
    SALT = auth['SALT']
    USER_ACCESS_TOKEN_EXPIRE_MINUTES = auth['USER_ACCESS_TOKEN_EXPIRE_MINUTES']
    BOT_ACCESS_TOKEN_EXPIRE_MINUTES = auth['BOT_ACCESS_TOKEN_EXPIRE_MINUTES']
    WEBSOCKET_TOKEN_EXPIRE_SECONDS = 30
    OAUTH2 = OAuth2PasswordBearer(tokenUrl=f"/{API.VERSION.value}/user/token")


class Default(Enum):
    DEFAULT_AVATAR = default['DEFAULT_AVATAR']
    DEFAULT_BIO = default['DEFAULT_BIO']


class Limits(Enum):
    AVATAR_SIZE_RANGE = limits['AVATAR_SIZE_RANGE']
    REASON_LENGTH_RANGE = limits['REASON_LENGTH_RANGE']
    USER_NAME_LENGTH_RANGE = limits['USER_NAME_LENGTH_RANGE']
    USER_PASSWORD_LENGTH_RANGE = {"MIN": 32, "MAX": 32}  # MD5的长度
    USER_BIO_LENGTH_RANGE = limits['USER_BIO_LENGTH_RANGE']
    GROUP_NAME_LENGTH_RANGE = limits['GROUP_NAME_LENGTH_RANGE']
    GROUP_QA_LENGTH_RANGE = limits['GROUP_QA_LENGTH_RANGE']
    GROUP_ANN_LENGTH_RANGE = limits['GROUP_ANN_LENGTH_RANGE']
    GROUP_AUDIO_LENGTH_RANGE = limits['GROUP_AUDIO_LENGTH_RANGE']
    GROUP_FILE_SIZE_RANGE = limits['GROUP_FILE_SIZE_RANGE']
    GROUP_TEXT_LENGTH_RANGE = limits['GROUP_TEXT_LENGTH_RANGE']
    GROUP_IMAGE_SIZE_RANGE = limits['GROUP_IMAGE_SIZE_RANGE']
    GROUP_BAN_MAX_TIME = {"MIN": 0, "MAX": int(limits["GROUP_BAN_MAX_TIME"])}
    MESSAGE_EXPIRE_MINUTES = limits['MESSAGE_EXPIRE_MINUTES']
    REQUEST_EXPIRE_MINUTES = limits['REQUEST_EXPIRE_MINUTES']
    NOTIFICATION_EXPIRE_MINUTES = limits['NOTIFICATION_EXPIRE_MINUTES']
    MAX_DEVICE = limits['MAX_DEVICE']
    MAX_ONLINE_DEVICE = limits['MAX_ONLINE_DEVICE']
    MESSAGE_RATE = limits['MESSAGE_RATE']

    FILE_TYPE = {"file", "audio"}  # 允许上传的文件类型
    MESSAGE_TYPE = {"text", "image", "file", "audio", "forwardFile", "revokeRequest"}   # 所有可发送的消息类型
