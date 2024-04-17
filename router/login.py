from uuid import uuid4
from datetime import datetime, timedelta

from const import API, Auth, Collection, Miscellaneous
from depend.depends import getSelfInfo, getUserInfo, checker, getUserInfoWithAvatar
from utils.helper import hashPassword, timestamp
from utils.wsConnectionMgr import SCM
from utils.createAccessToken import createAccessToken
from schema.user import UserSchema
from schema.payload import Register

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


loginRouter = APIRouter(prefix=f"/{API.version.value}/user", tags=['Login'])


@loginRouter.post('/register')
def register(registerInfo: Register):
    '''
    用户注册
    :param registerInfo: 用户名 + 密码
    :return: 创建的用户的uuid
    '''
    userName, password = registerInfo.userName, registerInfo.password
    hashedPassword = hashPassword(password)

    userID = str(uuid4().int)[::4]
    userInfo = UserSchema(
        uuid=userID,
        userName=userName,
        password=hashedPassword,
        avatar=Miscellaneous.DEFAULT_AVATAR.value,
        bio="",
        lastSeen=timestamp(),
        lastUpdate=timestamp(),
        groups=[],
    )

    Collection.COLL_ACC.value.add(dict(userInfo))

    return {"uuid": userID}


@loginRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends(), isBot: bool = False):
    '''
    表单验证
    :param formData: 表单
    :param isBot: 以Bot身份登录
    :return: JWT Token
    '''
    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": formData.username},
        {"password": 1}
    )

    if not userInfo:
        raise HTTPException(status_code=401, detail="用户名或密码不正确")

    hashedPassword = hashPassword(formData.password)

    if hashedPassword != userInfo["password"]:
        raise HTTPException(status_code=401, detail="用户名或密码不正确")

    accessTokenExpires = timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES.value)
    token = createAccessToken(
        {"uuid": formData.username, "bot": isBot},
        accessTokenExpires
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@loginRouter.get('/check')
def check(newToken=Depends(checker)):
    '''
    验证token是否有效
    :return: 按需刷新token
    '''
    return newToken


@loginRouter.get('/profile/me')
def profile(user: UserSchema = Depends(getSelfInfo)):
    '''
    获取自己的信息，不包括avatar和password，avatar通过GET profile/{uuid}获取
    '''
    groupInfoList = []
    for groupObjID in user.groups:
        groupInfo = Collection.COLL_GRP.value.query(
            {"_id": groupObjID},
            {"_id": 0, "group": 1, "lastUpdate": 1}
        )
        groupInfoList.append(groupInfo)
    user.groups = groupInfoList

    ret = dict(user)
    del ret["id"]

    return ret


@loginRouter.get('/profile/{uuid}')
def userInfo(userInfo: UserSchema = Depends(getUserInfoWithAvatar)):
    '''
    获取用户信息
    :param uuid: 用户uuid
    :return: 用户的userName, avatar, lastUpdate
    '''
    info = {
        "userName": userInfo.userName,
        "avatar": userInfo.avatar,
        "lastUpdate": userInfo.lastUpdate,
    }

    return dict(UserSchema.parse_obj(info))


@loginRouter.get('/current/{uuid}')
def getUserCurrentInfo(userCurrentInfo: UserSchema = Depends(getUserInfo)):
    '''
    获取用户当前信息
    :param uuid: 用户uuid
    :return: 用户的lastSeen, bio
    '''
    if userCurrentInfo.uuid in SCM:
        userCurrentInfo.lastSeen = "Online"

    info = {
        "bio": userCurrentInfo.bio,
        "lastSeen": userCurrentInfo.lastSeen,
    }

    return dict(UserSchema.parse_obj(info))
