from const import Collection, Auth

from jose import JWTError, jwt
from fastapi import Request, HTTPException, Depends

async def tokenDecode(request: Request, call_next):
    print(request)
    token = request.headers.get("Authorization", "").split("Bearer ")[-1]
    if not token:
        raise HTTPException(status_code=401, detail="Token not provided")

    try:
        payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=[Auth.ALGORITHM.value])
        user = await Collection.COLL_ACC.value.query(
            {"uuid": payload["uuid"]},
            {"_id": 0, "password": 0}
        )
        request.state.user = user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired")

    response = await call_next(request)
    return response