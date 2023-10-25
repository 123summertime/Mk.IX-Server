from typing import Dict, List
from datetime import datetime

from uuid import uuid4
from schema.message import MessageSchema
from utils.wsConnectionMgr import ConnectionManager, GroupConnections

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

wsRouter = APIRouter(tags=['websockets'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

CM = ConnectionManager()
DB = "UserInfo"
ACC = "Account"


@wsRouter.websocket("/ws")
async def GroupMessageSender(
        websocket: WebSocket,
        userID: str,
        groupID: str
        # token = OAuth2PasswordBearer(tokenUrl="./../token")
):

    if groupID not in CM.online:
        CM.addConnectedGroup(groupID)
    await CM.online[groupID].connect(websocket, userID)

    try:
        while True:
            msg = await websocket.receive_json()
            print(f"User: {userID} Group: {groupID} Msg: {msg}")
            await CM.online[msg['group']].sending(MessageSchema(
                time=str(datetime.now().timestamp()).replace(".", ""),
                type="text",
                sender=userID,
                payload=msg['payload']
            ), userID)
    except:
        CM.online[groupID].disconnect(websocket, userID)
