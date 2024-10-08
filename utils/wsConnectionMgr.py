from typing import List, Any
from collections import defaultdict

from fastapi import WebSocket

from public.const import Database
from schema.message import GetMessageSchema, SendMessageSchema, SysMessageSchema
from schema.storage import StorageSchema
from utils.checker import beforeSendCheck
from utils.crud import DB_CRUD, ACCOUNT, GROUP, CrudHelpers
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

# ------------------


# class GroupConnectionManagerV2:
#     def __init__(self, groupID):
#         self.groupID = groupID
#         self._onlineUsers = defaultdict(list)  # K: userID  V: websocket列表
#         self._currentGroupCollection = DB_CRUD(Database.STORAGE_DB.value, self.groupID, StorageSchema)
#
#     async def connected(self, websocket, userID):
#         self._onlineUsers[userID] = websocket
#
#         lastSeen = ACCOUNT.query(
#             {"uuid": userID},
#             {"lastSeen": 1}
#         ).lastSeen
#
#         messages = self._currentGroupCollection.queryMany(
#             {"time": {"$gt": lastSeen}},
#             {"_id": 0},
#         )
#
#         # 发送离线期间的消息
#         for msg in messages:
#             await websocket.send_json(SendMessageSchema(
#                 time=msg.time,
#                 type=msg.type,
#                 group=self.groupID,
#                 senderID=msg.senderID,
#                 senderKey=msg.senderKey,
#                 payload=msg.payload,
#             ).model_dump())
#
#     def disconnect(self, userID):
#         ...
#
#     def groupOnlineUserCount(self):
#         return len(self._onlineUsers)
#
#     def sendingMessage(self, uuid, payload):
#         ...

class GroupItem:
    def __init__(self, groupID):
        self.groupID = groupID
        self._collection = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
        self._userInGroup = set()

    def addUser(self, userID):
        self._userInGroup.add(userID)

    def removeUser(self, userID):
        self._userInGroup.remove(userID)

    @property
    def onlineUserList(self):
        return self._userInGroup

    @property
    def onlineUserCount(self):
        return len(self._userInGroup)

    @property
    def collectionCRUD(self):
        return self._collection


class WebsocketConnectionManager:
    def __init__(self):
        self._users = defaultdict(set)               # K: userID    V: set(deviceID)
        self._device: dict[str, WebSocket] = dict()  # K: deviceID  V: websocket
        self._groups: dict[str, GroupItem] = dict()  # K: groupID   V: GroupItem()
        self._userGroups = defaultdict(set)          # K: userID    V: set(groupID)

        '''
        userID ─── deviceID ─── websocket
           └────── groupID ──── groupItem
        '''

    def __contains__(self, userID):
        return userID in self._users

    def __repr__(self):
        return f"User: {self._users}\n Device: {self._device}\n Group: {self._groups}\n UserGroup: {self._userGroups}"

    def userJoinedGroup(self,
                        userID: str,
                        groupID: str):
        if userID in self._users:
            self._userGroups[userID].add(groupID)
            self._userConnectToGroupItem(userID, groupID)

    async def connect(self,
                      userID: str,
                      deviceID: str,
                      websocket: WebSocket,
                      subprotocol: str):
        await websocket.accept(subprotocol=subprotocol)

        self._users[userID].add(deviceID)
        self._device[deviceID] = websocket

        joinedGroups = ACCOUNT.query(
            {"uuid": userID},
            {"groups": 1},
        ).groups

        groupIDs = map(lambda i: CrudHelpers.groupObjectIDtoInfo(i).group, joinedGroups)
        for groupID in groupIDs:
            self._userConnectToGroupItem(userID, groupID)
        await self._postOfflineMessages(userID, groupIDs, deviceID, websocket)

    def _userConnectToGroupItem(self,
                                userID: str,
                                groupID: str):
        if groupID not in self._groups:
            self._groups[groupID] = GroupItem(groupID)
        self._groups[groupID].addUser(userID)
        self._userGroups[userID].add(groupID)

    async def _postOfflineMessages(self,
                                   userID: str,
                                   groupIDs: str,
                                   deviceID: str,
                                   websocket: WebSocket):
        lastSeen = ACCOUNT.query(
            {"uuid": userID},
            {"lastSeen": 1}
        ).lastSeen.get(deviceID, timestamp())

        for groupID in groupIDs:
            messages = self._groups[groupID].collectionCRUD.queryMany(
                {"time": {"$gt": lastSeen}},
                {"_id": 0},
            )
            for msg in messages:
                userInfo = ACCOUNT.query(
                    {"uuid": message.senderID},
                    {"_id": 0, "lastUpdate": 1}
                )
                m = SendMessageSchema(
                    time=msg.time,
                    type=msg.type,
                    group=groupID,
                    senderID=msg.senderID,
                    senderKey=userInfo.lastUpdate,
                    payload=msg.payload,
                )
                await websocket.send_json(m.model_dump())

    async def disconnectUser(self,
                             userID: str,
                             deviceID: str):
        '''
        用户断开ws连接
        '''
        # 尝试关闭ws连接
        try:
            ws = self._device[deviceID]
            await ws.close()
        except Exception as e:
            pass

        # 清理工作
        self._users[userID].remove(deviceID)
        if not self._users[userID]:  # 用户所有设备都下线时
            for groupID in self._userGroups[userID]:
                self._groups[groupID].removeUser(userID)
                if self._groups[groupID].onlineUserCount == 0:
                    del self._groups[groupID]
            del self._users[userID]
            del self._userGroups[userID]
        del self._device[deviceID]

    async def disconnectUserFromGroup(self,
                                      userID: str,
                                      groupID: str):
        groupItem = self._groups[groupID]
        groupItem.removeUser(userID)
        self._userGroups[userID].remove(groupID)

    async def disconnectGroup(self, groupID):
        groupItem = self._groups[groupID]
        for userID in groupItem.onlineUserList:
            self._userGroups[userID].remove(groupID)
        del self._groups[groupID]

    async def sendingSystemMessage(self,
                                   userID: str,
                                   message: SysMessageSchema):
        for device in self._users[userID]:
            ws = self._device[device]
            await ws.send_json(message.model_dump())

    async def sendingGroupMessage(self,
                                  userID: str,
                                  groupID: str,
                                  message: GetMessageSchema):
        if userID not in self._userGroups:
            return

        check = beforeSendCheck(userID, groupID, message)
        modify = beforeSendModify(userID, groupID, message)
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
            group=groupID,
            senderID=message.senderID,
            senderKey=userInfo.lastUpdate,
            payload=message.payload,
        ).model_dump()

        groupItem = self._groups[groupID]
        for userID in groupItem.onlineUserList:
            for device in self._users[userID]:
                ws = self._device[device]
                await ws.send_json(sendMessage)

        storageMessage = StorageSchema(
            time=message.time,
            type=message.type,
            senderID=message.senderID,
            payload=message.payload,
        ).model_dump()

        groupItem.collectionCRUD.add(storageMessage)


WCM = WebsocketConnectionManager()
