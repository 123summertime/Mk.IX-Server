import traceback

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, Header, WebSocketDisconnect

from depends.getInfo import getSelfInfo, getGroupInfo
from public.const import Auth, API
from public.stateCode import SystemMessageType
from schema.message import GetMessageSchema, MessagePayload, SysMessageSchema
from utils.crud import WS_TOKEN
from utils.helper import timestamp
from utils.wsConnectionMgr import WCM

wsRouter = APIRouter(prefix="/websocket", tags=['Websockets'])


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

    API.LOGGER.value.info(f"{info.uuid} 在 {info.device} 设备 上线")

    try:
        while True:
            try:
                message = await websocket.receive_json()
                time = timestamp()
                API.LOGGER.value.info(f"{info.uuid} 在 {message['group']} 发送了 {message['type']} 类型的消息({time})")
                getMessage = GetMessageSchema(
                    time=time,
                    type=message["type"],
                    group=message["group"],
                    senderID=info.uuid,
                    payload=MessagePayload.model_validate(message["payload"])
                )
                if not getMessage.payload.meta:
                    getMessage.payload.meta = dict()
                await WCM.sendingGroupMessage(info.uuid, message["group"], getMessage)
            except HTTPException:
                API.LOGGER.value.info(f"{info.uuid} 触发了速率限制")
                sysMsg = SysMessageSchema(
                    time=timestamp(),
                    type=SystemMessageType.FAIL.value,
                    payload="发送速度过快，请稍后再试",
                )
                await WCM.sendingSystemMessage(info.uuid, sysMsg)
    except WebSocketDisconnect:
        await WCM.disconnectUser(info.uuid, info.device)
        API.LOGGER.value.info(f"{info.uuid} 在 {info.device} 设备 下线")
    except Exception as e:
        error = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        API.LOGGER.value.error(f"wsConnectionMgr出现错误: {error}")
