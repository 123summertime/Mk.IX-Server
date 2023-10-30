from jose import jwt
from datetime import datetime

from const import Auth


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()
    encode["exp"] = datetime.utcnow() + expiresDelta
    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token
