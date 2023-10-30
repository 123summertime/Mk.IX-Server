from uuid import uuid4
from datetime import datetime, timedelta

from const import Auth, Collection
from depend.depends import getUserInfo
from utils.hash import hashPassword
from utils.createAccessToken import createAccessToken
from schema.login import RegisterSchema

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


loginRouter = APIRouter(tags=['Login'])


@loginRouter.post('/register')
def register(userName: str, password: str):
    hashedPassword = hashPassword(password)

    userID = str(uuid4().int)[::4]
    userInfo = RegisterSchema(
        uuid=userID,
        userName=userName,
        password=hashedPassword,
        avatar="",
    )
    Collection.COLL_ACC.value.add(dict(userInfo))

    return {"uuid": userID}


@loginRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends()):
    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": formData.username},
        {"_id": 0, "uuid": 1, "password": 1}
    )

    if not userInfo:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    hashedPassword = hashPassword(formData.password)

    if hashedPassword != userInfo["password"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    accessTokenExpires = timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES.value)
    token = createAccessToken(
        {"uuid": userInfo["uuid"]},
        accessTokenExpires
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@loginRouter.get('/profile')
def profile(user: RegisterSchema = Depends(getUserInfo)):
    return user
