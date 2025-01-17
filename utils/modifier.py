import traceback
import io
from datetime import datetime, timezone

from pydub import AudioSegment

from public import CheckerState, Database
from schema import GetMessageSchema, MessagePayload, StorageSchema, BroadcastMeta
from .crud import ACCOUNT, FS, DB_CRUD


def textMessageModifier(userID: str,
                        groupID: str,
                        message: GetMessageSchema) -> CheckerState:
    # if not message.payload.meta["encrypt"]:
    #     message.payload.content += "喵"  # 在句尾加"喵"
    return CheckerState.OK


def imageMessageModifier(userID: str,
                         groupID: str,
                         message: GetMessageSchema) -> CheckerState:
    return CheckerState.OK


def revokeMessageModifier(userID: str,
                          groupID: str,
                          message: GetMessageSchema) -> CheckerState:
    time = message.payload.content

    DB = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
    getMessage = DB.query(
        {"time": time}
    )
    if getMessage.type in ("audio", "file"):
        hashcode = getMessage.payload.content
        FS.update(
            hashcode,
            {"$inc": {f"group.{groupID}": -1}}
        )

    userinfo = ACCOUNT.query(
        {"uuid": userID},
        {"username": 1, "uuid": 1}
    )

    message.type = "revoke"
    message.payload = MessagePayload(
        content=f"{userinfo.username}撤回了一条{'' if userID == getMessage.senderID else '成员'}消息",
        meta=BroadcastMeta(
            operation="revoke",
            var={
                "time": time,
                "id": userinfo.uuid,
                "name": userinfo.username,
                "sender": getMessage.senderID,
            }
        )
    )

    DB.update(
        {"time": time},
        {"$set": {"type": message.type, "payload": message.payload.model_dump()}}
    )

    return CheckerState.OK


def forwardFileMessageModifier(userID: str,
                               groupID: str,
                               message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.NOT_EXIST

    FS.update(hashcode, {
        "$set": {"uploadDate": datetime.now(timezone.utc)},
        "$inc": {f"group.{groupID}": 1}
    })

    message.type = "file"
    message.payload.name = file.name
    message.payload.size = file.file.length
    message.payload.content = hashcode

    return CheckerState.OK


def audioFileMessageModifier(userID: str,
                             groupID: str,
                             message: GetMessageSchema) -> CheckerState:
    hashcode = message.payload.content
    file = FS.query(hashcode)
    if not file:
        return CheckerState.NOT_EXIST

    # 将语音分为chunkCount段，获取每段的音量大小，放入meta字段中
    try:
        audio = AudioSegment.from_file(io.BytesIO(file.file.read()))
        chunkCount = min(50, (len(audio) // 1000) + 2)
        chunkLength = len(audio) // chunkCount
        audioChunks = [audio[i: i + chunkLength].rms for i in range(0, len(audio), chunkLength)]
        maxVolume = max(audioChunks)
        volume = [v / maxVolume * 100 // 1 for v in audioChunks]
        message.payload.meta |= {
            "length": round(len(audio) / 1000, 2),
            "volume": volume
        }
        return CheckerState.OK
    except Exception as e:
        print(e)
        return CheckerState.UNKNOWN


def beforeSendingModify(userID: str,
                        groupID: str,
                        message: GetMessageSchema) -> CheckerState:
    '''
    如有必要，发送消息前对消息进行原地修改
    '''
    if "at" not in message.payload.meta:
        message.payload.meta["at"] = []
    if "encrypt" not in message.payload.meta:
        message.payload.meta["encrypt"] = False

    callFunction = {
        "text": textMessageModifier,
        "image": imageMessageModifier,
        "audio": audioFileMessageModifier,
        "revokeRequest": revokeMessageModifier,
        "forwardFile": forwardFileMessageModifier,
    }

    if message.type not in callFunction:
        return CheckerState.OK

    res = callFunction[message.type](userID, groupID, message)
    return res
