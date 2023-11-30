from uuid import uuid4
from typing import Dict, List
from jose import JWTError, jwt

from const import Auth
from depend.depends import checker
from schema.message import GetMessageSchema
from utils.helper import timestamp
from utils.wsConnectionMgr import ConnectionManager, GroupConnections

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, Depends
from fastapi.security import OAuth2PasswordBearer

wsRouter = APIRouter(tags=['websockets'])
CM = ConnectionManager()


@wsRouter.websocket("/ws")
async def GroupMessageSender(websocket: WebSocket, userID: str, groupID: str, token: str):
    # try:
    #     payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    # except JWTError:
    #     raise WebSocketException(code=4003, reason="Invalid credentials")
    # if payload["uuid"] != userID:
    #     raise WebSocketException(code=4003, reason="Invalid credentials")

    if groupID not in CM.online:
        CM.addConnectedGroup(groupID)
    await CM.online[groupID].connect(websocket, userID)

    try:
        while True:
            message = await websocket.receive_json()
            print(f"User: {userName} Group: {groupID} Msg: {message}")
            await CM.online[message["group"]].sending(GetMessageSchema(
                time=timestamp(),
                type="text",
                group=message["group"],
                senderID=userID,
                payload=message["payload"]
            ), userID)
    except Exception:
        CM.online[groupID].disconnect(websocket, userID)
