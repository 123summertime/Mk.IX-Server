from datetime import datetime, timedelta

from fastapi import HTTPException, Depends, Path
from jose import JWTError, jwt

from public.const import Auth
from schema.group import GroupSchema
from schema.user import UserSchema
from utils.crud import ACCOUNT, GROUP
from utils.helper import createAccessToken


def getGroupInfo(group: str = None) -> GroupSchema | None:
    '''
    从数据库中获取群的信息
    :param group: 群ID
    :return: 包含除了avatar的群信息
    '''
    if not group:
        return None

    groupInfo = GROUP.query(
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
    avatar = GROUP.query(
        {"group": group},
        {"avatar": 1}
    )
    others.avatar = avatar.avatar

    return others


def getUserInfo(uuid: str = None) -> UserSchema | None:
    '''
    从数据库中获取用户的信息
    :param uuid: 用户uuid
    :return: 包含除了password, avatar的用户信息
    '''
    if not uuid:
        return None

    userInfo = ACCOUNT.query(
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
    avatar = ACCOUNT.query(
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
        raise HTTPException(status_code=401, detail="无效的token")

    selfInfo = ACCOUNT.query(
        {"uuid": payload["uuid"]},
        {"password": 0, "avatar": 0},
    )

    return selfInfo


def checker(token: str = Depends(Auth.OAUTH2.value)):
    '''
    验证Token是否有效 并刷新Token
    :param token: JWT Token
    :return: 更新后的JWT Token
    '''
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="登录过期")

    newToken = {"refreshToken": createAccessToken(payload["uuid"], payload["isBot"])}
    return newToken
