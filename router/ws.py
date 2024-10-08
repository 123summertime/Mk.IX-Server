from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, Header

from depends.getInfo import getSelfInfo, getGroupInfo
from public.const import Auth
from schema.message import GetMessageSchema, MessagePayload
from utils.crud import WS_TOKEN
from utils.helper import timestamp
from utils.wsConnectionMgr import GCM, SCM, WCM

wsRouter = APIRouter(prefix="/websocket", tags=['Websockets'])


@wsRouter.websocket("/ws")
async def GroupMessageSender(websocket: WebSocket, userID: str, groupID: str, Sec_Websocket_Protocol=Header(None)):
    Authorization = Sec_Websocket_Protocol

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


@wsRouter.websocket('/connect')
async def websocketConnection(websocket: WebSocket, Sec_Websocket_Protocol=Header(None)):
    token = Sec_Websocket_Protocol
    info = WS_TOKEN.query({"token": token})
    time = timestamp()
    limit = Auth.WEBSOCKET_TOKEN_EXPIRE_SECONDS.value
    if not info or (int(time) - int(info.time)) // 1000 > limit:
        raise WebSocketException(code=4001, reason="无效的token")

    WS_TOKEN.delete({"token": token})
    await WCM.connect(info.uuid, info.device, websocket, token)

    try:
        while True:
            await websocket.receive_json()
    except Exception as e:
        print("WCM", e)
        await WCM.disconnectUser(info.uuid, info.device)
