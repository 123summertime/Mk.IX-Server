from uuid import uuid4
from typing import Dict, List
from jose import JWTError, jwt

from const import Auth
from depend.getInfo import checker
from schema.message import GetMessageSchema
from utils.helper import timestamp
from utils.wsConnectionMgr import GCM, SCM

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, Depends
from fastapi.security import OAuth2PasswordBearer

wsRouter = APIRouter(tags=['websockets'])


@wsRouter.websocket("/ws")
async def GroupMessageSender(websocket: WebSocket, userID: str, groupID: str, token: str):
    # try:
    #     payload = jwt.decode(token, Auth.SECRET_KEY.value, algorithms=Auth.ALGORITHM.value)
    # except JWTError:
    #     raise WebSocketException(code=4003, reason="Invalid credentials")
    # if payload["uuid"] != userID:
    #     raise WebSocketException(code=4003, reason="Invalid credentials")

    # TODO: 检查是否在群中

    if groupID not in GCM.online:
        GCM.addConnectedGroup(groupID)
    await GCM.online[groupID].connect(websocket, userID)

    try:
        while True:
            message = await websocket.receive_json()
            print(f"User: {userID} Group: {groupID} Type: {message['type']} Payload: {message['payload'][:30]}")
            getMessage = GetMessageSchema(
                time=timestamp(),
                type=message["type"],
                group=message["group"],
                senderID=userID,
                payload=message["payload"]
            )
            await GCM.online[groupID].sending(websocket, userID, getMessage)

    except Exception as e:
        print("GCM", groupID, e)
        GCM.online[groupID].disconnect(userID)


@wsRouter.websocket('/wsSys')
async def SystemMessageSender(websocket: WebSocket, userID: str, token: str):
    # TODO: 验证

    await SCM.connect(websocket, userID)
    try:
        while True:
            await websocket.receive_json()
    except Exception as e:
        print("SCM", e)
        SCM.disconnect(userID)
