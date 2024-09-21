import hashlib
from datetime import datetime, timedelta

from jose import jwt

from public.const import Auth


def hashPassword(password: str) -> str:
    withSalt = password + Auth.SALT.value
    return hashlib.sha256(withSalt.encode()).hexdigest()


def timestamp() -> str:
    return ("{:.3f}".format(datetime.now().timestamp())).replace(".", "")


def createAccessToken(uuid, isBot) -> str:
    encode = {"uuid": uuid, "isBot": isBot}

    if isBot:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.BOT_ACCESS_TOKEN_EXPIRE_MINUTES.value)
    else:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.USER_ACCESS_TOKEN_EXPIRE_MINUTES.value)

    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token
