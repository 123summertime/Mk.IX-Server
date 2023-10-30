from const import Collection, Auth

from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer


def getUserInfo(token: str = Depends(Auth.OAUTH2.value)):
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired")
    userInfo = Collection.COLL_ACC.value.query(
        {"uuid": payload["uuid"]},
        {"_id": 0, "password": 0}
    )
    return userInfo
