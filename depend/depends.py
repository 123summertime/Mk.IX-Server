from datetime import datetime, timedelta

from const import Collection, Auth
from utils.createAccessToken import createAccessToken

from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer


def getUserInfo(token: str = Depends(Auth.OAUTH2.value)):
    '''
    验证通过后从数据库中获取用户信息
    :param token: JWT Token
    :return: 包含除了password, avatar的用户信息
    '''
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired")

    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": payload["uuid"]},
        {"password": 0, "avatar": 0},
    )

    return userInfo


def checker(token: str = Depends(Auth.OAUTH2.value)):
    '''
    验证Token是否有效 并按需刷新Token
    :param token: JWT Token
    :return: 空字符串或更新后的Token
    '''
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired")

    # token在6h内过期, 自动续token
    rt = {"refreshToken": ""}
    if datetime.now() <= datetime.fromtimestamp(payload["exp"]) <= datetime.now() + timedelta(hours=6):
        rt["refreshToken"] = createAccessToken(
            {"uuid": payload["uuid"], "bot": payload["bot"]},
            timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES.value),
        )

    return rt
