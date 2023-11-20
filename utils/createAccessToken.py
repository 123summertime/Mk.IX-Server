from jose import jwt
from datetime import datetime, timedelta

from const import Auth


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()
    if data["bot"] == "1":
        encode["exp"] = datetime.utcnow() + timedelta(minutes=525600)
    else:
        encode["exp"] = datetime.utcnow() + expiresDelta
    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token
