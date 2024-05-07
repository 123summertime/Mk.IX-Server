from datetime import datetime, timedelta

from fastapi import HTTPException, Depends, Path
from jose import JWTError, jwt

from public.const import Auth
from public.instance import Collection
from schema.group import GroupSchema
from schema.user import UserSchema
from utils.createAccessToken import createAccessToken


def getGroupInfo(group: str = Path(...)) -> GroupSchema:
    '''
    从数据库中获取群的信息
    :param group: 群ID 从路径中获取
    :return: 包含除了avatar的群信息
    '''
    groupInfo = Collection.GROUP.value.query(
        {"group": group},
        {"avatar": 0}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")

    return groupInfo


def getGroupInfoWithAvatar(group: str = Path(...),
                           others: GroupSchema = Depends(getGroupInfo)) -> GroupSchema:
    '''
    在getGroupInfo的基础上加上avatar
    '''
    avatar = Collection.GROUP.value.query(
        {"group": group},
        {"avatar": 1}
    )
    others.avatar = avatar.avatar

    return others


def getUserInfo(uuid: str = Path(...)) -> UserSchema:
    '''
    从数据库中获取用户的信息
    :param uuid: 用户uuid 从路径中获取
    :return: 包含除了password, avatar的用户信息
    '''
    userInfo = Collection.ACCOUNT.value.query(
        {"uuid": uuid},
        {"password": 0, "avatar": 0},
    )

    if not userInfo:
        raise HTTPException(status_code=400, detail="用户不存在")

    return userInfo


def getUserInfoWithAvatar(uuid: str = Path(...),
                          others: UserSchema = Depends(getUserInfo)) -> UserSchema:
    '''
    在getUserInfo的基础上加上avatar
    '''
    avatar = Collection.ACCOUNT.value.query(
        {"uuid": uuid},
        {"avatar": 1},
    )
    others.avatar = avatar.avatar

    return others


def getSelfInfo(token: str = Depends(Auth.OAUTH2.value)) -> UserSchema:
    '''
    验证通过后从数据库中获取用户信息，token必须有效
    :param token: JWT Token
    :return: 包含除了password, avatar的用户信息
    '''
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="token无效")

    selfInfo = Collection.ACCOUNT.value.query(
        {"uuid": payload["uuid"]},
        {"password": 0, "avatar": 0},
    )

    return selfInfo


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
