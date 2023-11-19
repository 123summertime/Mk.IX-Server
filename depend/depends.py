from datetime import datetime, timedelta

from const import Collection, Auth
from utils import createAccessToken

from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer


def getUserInfo(token: str = Depends(Auth.OAUTH2.value)):
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired")

    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": payload["uuid"]},
        {"_id": 0, "password": 0},
    )

    # token在3h内过期, 自动续token
    userInfo["refreshToken"] = ""
    if datetime.now() <= datetime.fromtimestamp(payload["exp"]) <= datetime.now() + timedelta(hours=3):
        userInfo["refreshToken"] = createAccessToken(
            {"uuid": userInfo["uuid"]},
            timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES.value)
        )

    return userInfo


def checker(token: str = Depends(Auth.OAUTH2.value)):
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired")
    return True
