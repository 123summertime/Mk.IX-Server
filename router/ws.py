from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, Header

from depends.getInfo import getSelfInfo, getGroupInfo
from schema.message import GetMessageSchema, MessagePayload
from utils.helper import timestamp
from utils.wsConnectionMgr import GCM, SCM

wsRouter = APIRouter(prefix="/ws", tags=['Websockets'])


@wsRouter.websocket("/ws")
async def GroupMessageSender(websocket: WebSocket, userID: str, groupID: str, Sec_Websocket_Protocol=Header(None)):
    Authorization = Sec_Websocket_Protocol  # 你以为是subprotocol? 其实是我Authorization哒

    try:
        userInfo = getSelfInfo(Authorization)
        groupInfo = getGroupInfo(groupID)
        if userInfo.id not in groupInfo.user:
            raise HTTPException(403)
    except HTTPException:
        raise WebSocketException(code=4003, reason="Token已过期或未加入该群聊")

    await GCM.addConnectedUser(groupID, websocket, userID, Authorization)

    try:
        while True:
            message = await websocket.receive_json()
            print(f"User: {userID} Group: {groupID} Type: {message['type']} Payload: {message['payload']['content'][:30]}")
            getMessage = GetMessageSchema(
                time=timestamp(),
                type=message["type"],
                group=groupID,
                senderID=userID,
                payload=MessagePayload.model_validate(message["payload"])
            )
            await GCM.sending(groupID, userID, getMessage)

    except Exception as e:
        # traceback.print_exc()
        print("GCM", groupID, e)
        await GCM.removeUser(groupID, userID)


@wsRouter.websocket('/systemWS')
async def SystemMessageSender(websocket: WebSocket, userID: str, Sec_Websocket_Protocol=Header(None)):
    Authorization = Sec_Websocket_Protocol

    try:
        getSelfInfo(Authorization)
    except HTTPException as e:
        raise WebSocketException(code=4003, reason="Token已过期")

    await SCM.connect(websocket, userID, Authorization)

    try:
        while True:
            await websocket.receive_json()
    except Exception as e:
        print("SCM", e)
        await SCM.disconnect(userID)
