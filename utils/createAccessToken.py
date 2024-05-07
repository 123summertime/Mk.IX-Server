from datetime import datetime, timedelta

from jose import jwt

from public.const import Auth


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()

    if data["bot"]:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.BOT_ACCESS_TOKEN_EXPIRE_MINUTES.value)
    else:
        encode["exp"] = datetime.utcnow() + timedelta(minutes=Auth.USER_ACCESS_TOKEN_EXPIRE_MINUTES.value)

    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)

    return token
