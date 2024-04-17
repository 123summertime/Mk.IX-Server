from datetime import datetime, timedelta

from const import Collection, Auth
from utils.createAccessToken import createAccessToken
from schema.payload import GroupID
from schema.user import UserSchema
from schema.group import GroupSchema

from jose import JWTError, jwt
from fastapi import HTTPException, Depends, Path
from fastapi.security import OAuth2PasswordBearer


def getGroupInfo(group: str = Path(...)):
    '''
    从数据库中获取群的信息
    :param group: 群ID 从路径中获取
    :return: 包含除了avatar的群信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"avatar": 0}
    )

    if not groupInfo:
        return None

    return GroupSchema.parse_obj(groupInfo)


def getGroupInfoWithAvatar(group: str = Path(...), others: GroupSchema = Depends(getGroupInfo)):
    '''
    在getGroupInfo的基础上加上avatar
    '''
    if not others:
        return None

    avatar = Collection.COLL_GRP.value.query(
        {"group": group},
        {"avatar": 1}
    )
    others.avatar = avatar["avatar"]

    return others


def getUserInfo(uuid: str = Path(...)):
    '''
    从数据库中获取用户的信息
    :param uuid: 用户uuid 从路径中获取
    :return: 包含除了password, avatar的用户信息
    '''
    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": uuid},
        {"password": 0, "avatar": 0},
    )

    if not userInfo:
        return None

    return UserSchema.parse_obj(userInfo)


def getUserInfoWithAvatar(uuid: str = Path(...), others: UserSchema = Depends(getUserInfo)):
    '''
    在getUserInfo的基础上加上avatar
    '''
    if not others:
        return None

    avatar = Collection.COLL_ACC.value.query(
        {"uuid": uuid},
        {"avatar": 1},
    )
    others.avatar = avatar["avatar"]

    return others


def getSelfInfo(token: str = Depends(Auth.OAUTH2.value)):
    '''
    验证通过后从数据库中获取用户信息，token必须有效
    :param token: JWT Token
    :return: 包含除了password, avatar的用户信息
    '''
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="token无效")

    selfInfo = Collection.COLL_ACC.value.query(
        {"uuid": payload["uuid"]},
        {"password": 0, "avatar": 0},
    )

    return UserSchema.parse_obj(selfInfo)


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
