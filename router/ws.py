from depend.getInfo import getSelfInfo
from schema.message import GetMessageSchema
from utils.helper import timestamp
from utils.wsConnectionMgr import GCM, SCM

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, Header

wsRouter = APIRouter(prefix="/ws", tags=['Websockets'])


@wsRouter.websocket("/ws")
async def GroupMessageSender(websocket: WebSocket, userID: str, groupID: str, Sec_Websocket_Protocol=Header(None)):
    Authorization = Sec_Websocket_Protocol  # 你以为是subprotocol? 其实是我Authorization哒

    try:
        getSelfInfo(Authorization)
    except HTTPException as e:
        raise WebSocketException(code=4003, reason="Invalid credentials")

    if groupID not in GCM.online:
        GCM.addConnectedGroup(groupID)
    await GCM.online[groupID].connect(websocket, userID, Authorization)

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
async def SystemMessageSender(websocket: WebSocket, userID: str, Sec_Websocket_Protocol=Header(None)):
    Authorization = Sec_Websocket_Protocol

    try:
        getSelfInfo(Authorization)
    except HTTPException as e:
        raise WebSocketException(code=4003, reason="Invalid credentials")

    await SCM.connect(websocket, userID, Authorization)
    try:
        while True:
            await websocket.receive_json()
    except Exception as e:
        print("SCM", e)
        SCM.disconnect(userID)
