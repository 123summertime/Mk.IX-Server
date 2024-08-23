from public.const import Database
from schema.message import GetMessageSchema, SendMessageSchema, SysMessageSchema
from schema.storage import StorageSchema
from utils.checker import beforeSendCheck
from utils.crud import DB_CRUD, ACCOUNT, GROUP
from utils.helper import timestamp
from utils.modifier import beforeSendModify


class GroupConnectionManager:
    '''
    所有群的websocket
    '''
    def __init__(self):
        self._online = dict()

    def addConnectedGroup(self, groupID):
        exist = GROUP.query(
            {"group": groupID},
            {"_id": 1}
        )

        if not exist:
            raise RuntimeError(f"群{groupID}不存在")

        self._online[groupID] = GroupConnections(groupID)

    async def removeGroup(self, groupID):
        if groupID in self._online:
            await self._online[groupID].disconnectAll()
            del self._online[groupID]

    async def addConnectedUser(self, groupID, websocket, userID, Authorization):
        if groupID not in self._online:
            self.addConnectedGroup(groupID)
        await self._online[groupID].connect(websocket, userID, Authorization)

    async def removeUser(self, groupID, uuid):
        if groupID in self._online:
            await self._online[groupID].disconnect(uuid)

    async def sending(self, groupID, userID, message):
        if groupID not in self._online:
            self.addConnectedGroup(groupID)
        await self._online[groupID].sending(userID, message)


class GroupConnections:
    '''
    一个群的websocket 在群里发送信息将在这里处理
    '''
    def __init__(self, groupID):
        self.groupID = groupID
        self._connections = dict()  # K: userID  V: wsConnection
        self._currentGroupCollection = DB_CRUD(Database.STORAGE_DB.value, self.groupID, StorageSchema)

    def __repr__(self):
        return f"{self.groupID}:\n" \
               f"Online Users {self._connections}\n"

    async def connect(self, websocket, userID, subprotocol):
        await websocket.accept(subprotocol=subprotocol)

        lastSeen = ACCOUNT.query(
            {"uuid": userID},
            {"lastSeen": 1}
        ).lastSeen

        messages = self._currentGroupCollection.queryMany(
            {"time": {"$gt": lastSeen}},
            {"_id": 0},
        )

        # 发送离线期间的消息
        for msg in messages:
            await websocket.send_json(SendMessageSchema(
                time=msg.time,
                type=msg.type,
                group=self.groupID,
                senderID=msg.senderID,
                senderKey=msg.senderKey,
                payload=msg.payload,
            ).model_dump())

        self._connections[userID] = websocket

    async def disconnect(self, userID):
        if userID in self._connections:
            ACCOUNT.update(
                {"uuid": userID},
                {"$set": {"lastSeen": timestamp()}},
            )

            await self._connections[userID].close()
            del self._connections[userID]

    async def disconnectAll(self):
        for ws in self._connections.values():
            await ws.close()

    async def sending(self, userID: str, message: GetMessageSchema):
        check = beforeSendCheck(userID, self.groupID, message)
        modify = beforeSendModify(userID, self.groupID, message)
        result = check and modify
        if not result:
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type="fail",
                payload=result.value
            )
            await SCM.sending(userID, sysMsg)
            return

        userInfo = ACCOUNT.query(
            {"uuid": message.senderID},
            {"_id": 0, "lastUpdate": 1}
        )

        sendMessage = SendMessageSchema(
            time=message.time,
            type=message.type,
            group=self.groupID,
            senderID=message.senderID,
            senderKey=userInfo.lastUpdate,
            payload=message.payload,
        )

        storageMessage = StorageSchema(
            time=message.time,
            type=message.type,
            senderID=message.senderID,
            senderKey=userInfo.lastUpdate,
            payload=message.payload,
        )

        self._currentGroupCollection.add(storageMessage.model_dump())
        for ws in self._connections.values():
            await ws.send_json(sendMessage.model_dump())


class SystemConnectionManager:
    '''
    系统通知websocket 如:群验证消息，群消息发送失败...
    '''
    def __init__(self):
        self._connections = dict()  # K: userID  V: wsConnection

    def __contains__(self, uuid):
        return uuid in self._connections

    async def connect(self, websocket, userID, subprotocol):
        await websocket.accept(subprotocol=subprotocol)
        self._connections[userID] = websocket

    async def disconnect(self, userID):
        if userID in self._connections:
            await self._connections[userID].close()
            del self._connections[userID]

    async def sending(self, userID, payload):
        if userID in self._connections:
            ws = self._connections[userID]
            await ws.send_json(payload.model_dump())


GCM = GroupConnectionManager()
SCM = SystemConnectionManager()
