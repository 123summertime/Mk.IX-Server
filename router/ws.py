import asyncio
import traceback

from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, Header, WebSocketDisconnect

from public import Auth, API, SystemMessageType
from schema import GetMessageSchema, SysMessageSchema
from utils import WS_TOKEN, timestamp, WCM

wsRouter = APIRouter(prefix="/websocket", tags=['Websockets'])


@wsRouter.websocket('/connect')
async def websocketConnection(websocket: WebSocket,
                              Sec_Websocket_Protocol=Header(None),
                              Authorization=Header(None)):
    token = Sec_Websocket_Protocol or Authorization  # 任选其一传递token
    info = WS_TOKEN.query({"token": token})
    time = timestamp()
    limit = Auth.WEBSOCKET_TOKEN_EXPIRE_SECONDS.value
    if not info or (int(time) - int(info.time)) // 1000 > limit:
        raise WebSocketException(code=4001, reason="无效的token")

    WS_TOKEN.delete({"token": token})
    await WCM.connect(info.uuid, info.device, websocket, Sec_Websocket_Protocol, Authorization)

    API.LOGGER.value.info(f"{info.uuid} 在 {info.device} 设备 上线")

    try:
        while True:
            try:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    raise ValueError
                time = timestamp()
                message["time"] = time
                message["senderID"] = info.uuid
                getMessage = GetMessageSchema.model_validate(message)
                if not getMessage.payload.meta:
                    getMessage.payload.meta = dict()
                API.LOGGER.value.info(f"{info.uuid} 在 {getMessage.group}({getMessage.groupType}) 发送了 {getMessage.type} 类型的消息 ({time})")
                asyncio.create_task(WCM.sendingGroupMessage(info.uuid, getMessage, info.device))
            except HTTPException:
                API.LOGGER.value.info(f"{info.uuid} 触发了速率限制")
                sysMsg = SysMessageSchema(
                    time=timestamp(),
                    type=SystemMessageType.FAIL.value,
                    payload="发送速度过快，请稍后再试",
                )
                await WCM.sendingSystemMessage(info.uuid, sysMsg)
            except ValidationError:
                API.LOGGER.value.info(f"{info.uuid} 发送了无效的消息")
            except ValueError:
                API.LOGGER.value.info(f"{info.uuid} 发送了无效的消息")
    except WebSocketDisconnect:
        await WCM.disconnectUser(info.uuid, info.device)
        API.LOGGER.value.info(f"{info.uuid} 在 {info.device} 设备 下线")
    except Exception as e:
        error = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        API.LOGGER.value.error(f"wsConnectionMgr出现错误: {error}")
