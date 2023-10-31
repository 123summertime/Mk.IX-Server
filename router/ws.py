from typing import Dict, List
from datetime import datetime

from uuid import uuid4
from schema.message import MessageSchema
from utils.wsConnectionMgr import ConnectionManager, GroupConnections

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketException, Depends
from fastapi.security import OAuth2PasswordBearer

wsRouter = APIRouter(tags=['websockets'])

CM = ConnectionManager()


@wsRouter.websocket("/ws")
async def GroupMessageSender(
        websocket: WebSocket,
        userID: str,
        groupID: str
        # token
):

    if groupID not in CM.online:
        CM.addConnectedGroup(groupID)
    await CM.online[groupID].connect(websocket, userID)

    try:
        while True:
            message = await websocket.receive_json()
            print(f"User: {userID} Group: {groupID} Msg: {message}")
            await CM.online[message['group']].sending(MessageSchema(
                time=str(datetime.now().timestamp()).replace(".", ""),
                type="text",
                sender=userID,
                payload=message['payload']
            ), userID)
    except Exception:
        CM.online[groupID].disconnect(websocket, userID)
