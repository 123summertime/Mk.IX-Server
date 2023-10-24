import pprint
import copy
from uuid import uuid4
from utils import dbCRUD
from typing import Dict, List
from datetime import datetime
from schema.message import MessageSchema
from utils.wsConnectionMgr import ConnectionManager, GroupConnections
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketException, Depends

app = FastAPI()
wsRouter = APIRouter(tags=['websockets'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

CM = ConnectionManager()
DB = "UserInfo"
COLLECTION = "Account"


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

    for x in CM.online:
        print("Group", x, "WS", CM.online[x].onlineUsers, CM.online[x].allUsers)

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
