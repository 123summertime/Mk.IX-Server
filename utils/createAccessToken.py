from jose import jwt
from datetime import datetime

from const import Auth


def createAccessToken(data: dict, expiresDelta, isBot):
    encode = data.copy()
    if isBot:
        encode["exp"] = datetime.utcnow() + 525600
    else:
        encode["exp"] = datetime.utcnow() + expiresDelta
    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token
