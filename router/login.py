from uuid import uuid4
from datetime import datetime, timedelta

from const import Auth, Collection
from middleware import tokenDecode
from utils.hash import hashPassword
from schema.login import RegisterSchema

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


loginRouter = APIRouter(tags=['Login'])
OAUTH2 = OAuth2PasswordBearer(tokenUrl="token")


@loginRouter.post('/register')
def register(userName: str, password: str, s: RegisterSchema):
    hashedPassword = hashPassword(password)

    s = RegisterSchema(
        uuid=str(uuid4().int)[::4],
        userName=userName,
        password=hashedPassword,
        avatar="",
    )

    feedback = Collection.COLL_ACC.value.add(dict(s))
    return feedback


def getUserInfo(user_uuid):
    return Collection.COLL_ACC.value.query(
        {"uuid": user_uuid},
        {"_id": 0, "uuid": 1, "password": 1}
    )


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()
    encode["exp"] = datetime.utcnow() + expiresDelta
    token = jwt.encode(encode, Auth.SECRET_KEY.value, algorithm=Auth.ALGORITHM.value)
    return token


@loginRouter.post('/token')
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    userInfo = getUserInfo(form_data.username)

    if not userInfo:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    hashedPassword = hashPassword(form_data.password)

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


def tokenDecode(uid):
    return Collection.COLL_ACC.value.query(
        {"uuid": uid},
        {"_id": 0, "password": 0}
    )


def getCurrentUser(token: str = Depends(OAUTH2)):
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
        uid = payload["uuid"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired")
    return tokenDecode(uid)


@loginRouter.get('/profile')
def profile(user: RegisterSchema = Depends(getCurrentUser)):
    return user
