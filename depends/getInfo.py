from fastapi import HTTPException, Depends, Path
from jose import JWTError, jwt

from public import Auth, Limits, RequestState
from schema import GroupSchema, UserSchema, RequestMsgSchema
from utils import ACCOUNT, GROUP, GROUP_REQUEST, FRIEND_REQUEST, createAccessToken, timestamp


def getGroupInfo(group: str = Path(...)) -> GroupSchema:
    '''
    从数据库中获取群的信息
    :param group: 群ID
    :return: 包含除了avatar的群信息
    '''
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


def getUserInfo(uuid: str = Path(...)) -> UserSchema:
    '''
    从数据库中获取用户的信息
    :param uuid: 用户uuid
    :return: 包含除了password, avatar的用户信息
    '''
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
    if not selfInfo:
        raise HTTPException(status_code=404, detail="用户不存在")
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


def getSelfRequest(userInfo: UserSchema = Depends(getSelfInfo),
                   groupInfo: GroupSchema = Depends(getGroupInfo)) -> RequestMsgSchema | None:
    requestInfo = GROUP_REQUEST.query(
        {"senderID": userInfo.uuid, "target": groupInfo.group},
        {"_id": 0}
    )

    # 排除过期请求
    if requestInfo and int(timestamp()) - int(requestInfo.time) > int(Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000):
        return None
    return requestInfo


def getUserRequest(time: str = Path(...)) -> RequestMsgSchema | None:
    requestInfo = GROUP_REQUEST.query(
        {"time": time},
        {"_id": 0}
    )

    # 排除过期请求
    if requestInfo and int(timestamp()) - int(time) > int(Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000):
        raise None
    return requestInfo


def getRequest(userInfo: UserSchema,
               isGroupRequest: bool,
               target: str = None,
               time: str = None) -> RequestMsgSchema | None:
    collection = GROUP_REQUEST if isGroupRequest else FRIEND_REQUEST
    query = {"time": time} if time else {"senderID": userInfo.uuid, "target": target}
    res = collection.queryMany(query, {"_id": 0})
    if time:
        return res[0] if res else None
    for req in res:
        if req.state == RequestState.PENDING.value:
            return req
    return None
