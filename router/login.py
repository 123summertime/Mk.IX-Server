import random
from uuid import uuid4
from jose import JWTError, jwt
from utils import dbCRUD, hash
from schema.login import RegisterSchema
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


loginRouter = APIRouter(tags=['Login'])

SECRET_KEY = "hw4jf6uz8o4na1rc3pf9yxr8fn3gft3m"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2160
DB = "UserInfo"
COLLECTION = "Account"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")



@loginRouter.post('/register')
async def register(userName: str, password: str, s: RegisterSchema):
    hashedPassword = hash.hashPassword(password)

    s = RegisterSchema(
        uuid=str(uuid4().int)[::4],
        userName=userName,
        password=hashedPassword,
        avatar="",
    )

    feedback = dbCRUD.DB_CRUD(DB, COLLECTION).add(dict(s))
    return feedback


def getUserInfo(user_uuid):
    return dbCRUD.DB_CRUD(DB, COLLECTION).query(
        {"uuid": user_uuid},
        {"_id": 0, "uuid": 1, "password": 1}
    )


def createAccessToken(data: dict, expiresDelta):
    encode = data.copy()
    encode["exp"] = datetime.utcnow() + expiresDelta
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


@loginRouter.post('/token')
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    userInfo = getUserInfo(form_data.username)

    if not userInfo:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    hashedPassword = hash.hashPassword(form_data.password)

    if hashedPassword != userInfo["password"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    accessTokenExpires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = createAccessToken(
        {"uuid": userInfo["uuid"]},
        accessTokenExpires
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


def tokenDecode(uid):
    return dbCRUD.DB_CRUD(DB, COLLECTION).query(
        {"uuid": uid},
        {"_id": 0, "password": 0}
    )


def getCurrentUser(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        uid = payload["uuid"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired")
    return tokenDecode(uid)


@loginRouter.get('/profile')
async def profile(user: RegisterSchema = Depends(getCurrentUser)):
    return user
