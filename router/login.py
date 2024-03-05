from uuid import uuid4
from datetime import datetime, timedelta

from const import Auth, Collection, Miscellaneous
from depend.depends import getUserInfo, checker
from utils.helper import hashPassword, timestamp
from utils.createAccessToken import createAccessToken
from schema.user import UserSchema

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


loginRouter = APIRouter(tags=['Login'])


@loginRouter.post('/register')
def register(userName: str, password: str):
    '''
    用户注册
    :param userName: 用户名
    :param password: 密码
    :return: 创建的用户的uuid
    '''
    hashedPassword = hashPassword(password)

    userID = str(uuid4().int)[::4]
    userInfo = UserSchema(
        uuid=userID,
        userName=userName,
        password=hashedPassword,
        avatar=Miscellaneous.DEFAULT_AVATAR.value,
        lastSeen=timestamp(),
        lastUpdate=timestamp(),
        groups=[],
    )

    Collection.COLL_ACC.value.add(dict(userInfo))

    return {
        "uuid": userID
    }


@loginRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends(), isBot: str = "0"):
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
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    hashedPassword = hashPassword(formData.password)

    if hashedPassword != userInfo["password"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    accessTokenExpires = timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES.value)
    token = createAccessToken(
        {"uuid": formData.username, "bot": isBot},
        accessTokenExpires
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@loginRouter.get('/profile')
def profile(user: UserSchema = Depends(getUserInfo)):
    del user["_id"]
    groupInfoList = []
    for groupObjID in user["groups"]:
        groupInfo = Collection.COLL_GRP.value.query(
            {"_id": groupObjID},
            {"_id": 0, "group": 1, "lastUpdate": 1}
        )
        groupInfoList.append(groupInfo)
    user["groups"] = groupInfoList
    return user


@loginRouter.get('/check')
def check(newToken=Depends(checker)):
    return newToken


@loginRouter.get('/getUserInfo')
def getUserInfo(uuid: str):
    '''
    获取用户信息
    :param uuid: 用户uuid
    :return: 用户的userName,avatar,lastUpdate
    '''
    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": uuid},
        {"_id": 0, "userName": 1, "avatar": 1, "lastUpdate": 1}
    )
    return userInfo
