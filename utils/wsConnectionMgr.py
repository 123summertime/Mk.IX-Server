from typing import List, Any
from collections import defaultdict

from fastapi import WebSocket

from public.const import Database, Limits
from public.stateCode import SystemMessageType
from schema.message import GetMessageSchema, SendMessageSchema, SysMessageSchema
from schema.storage import StorageSchema, NotificationMsgSchema
from utils.checker import beforeSendingCheck
from utils.crud import DB_CRUD, ACCOUNT, GROUP, CrudHelpers
from utils.helper import timestamp
from utils.modifier import beforeSendingModify


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

    def _userConnectToGroupItem(self,
                                userID: str,
                                groupID: str):
        if groupID not in self._groups:
            self._groups[groupID] = GroupItem(groupID)
        self._groups[groupID].addUser(userID)
        self._userGroups[userID].add(groupID)

    async def connect(self,
                      userID: str,
                      deviceID: str,
                      websocket: WebSocket,
                      subprotocol: str):
        await websocket.accept(subprotocol=subprotocol)

        self._users[userID].add(deviceID)
        self._device[deviceID] = websocket

        userInfo = ACCOUNT.query(
            {"uuid": userID},
            {"groups": 1, "lastSeen": 1},
        )

        groupIDs = list(map(lambda i: CrudHelpers.groupObjectIDtoInfo(i).group, userInfo.groups))
        for groupID in groupIDs:
            self._userConnectToGroupItem(userID, groupID)

        lastSeen = userInfo.lastSeen.get(deviceID, timestamp())
        await self._postOfflineNotificationMessages(userID, lastSeen, websocket)
        await self._postOfflineGroupMessages(groupIDs, lastSeen, websocket)

    async def _postOfflineNotificationMessages(self,
                                               userID: str,
                                               lastSeen: str,
                                               websocket: WebSocket):
        collection = DB_CRUD(Database.NotificationDB.value, userID, NotificationMsgSchema)
        messages = collection.queryMany(
            {"target": userID, "time": {"$gt": lastSeen}},
            {"_id": 0},
        )

        for msg in messages:
            targetInfo = (GROUP if msg.isGroupMessage else ACCOUNT).query(
                {("group" if msg.isGroupMessage else "uuid"): msg.blank},
                {("name" if msg.isGroupMessage else "username"): 1},
            )
            newPayload = msg.payload.format(targetInfo.name if msg.isGroupMessage else targetInfo.username)
            m = SysMessageSchema(
                time=msg.time,
                type=msg.type,
                subType=msg.subType,
                payload=newPayload,
            )
            try:
                await websocket.send_json(m.model_dump())
            except Exception as e:
                print("Exception on sending notification message ->", e)

    async def _postOfflineGroupMessages(self,
                                        groupIDs: list,
                                        lastSeen: str,
                                        websocket: WebSocket):
        '''
        发送用户离线时收到的消息
        '''
        for groupID in groupIDs:
            messages = self._groups[groupID].collectionCRUD.queryMany(
                {"time": {"$gt": lastSeen}},
                {"_id": 0},
            )

            for msg in messages:
                userInfo = ACCOUNT.query(
                    {"uuid": msg.senderID},
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
                try:
                    await websocket.send_json(m.model_dump())
                except Exception as e:
                    print("Exception on sending offline message ->", e)

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

        # 更新device的lastSeen
        ACCOUNT.update(
            {"uuid": userID},
            {"$set": {f"lastSeen.{deviceID}": timestamp()}}
        )

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

    async def sendingNotificationMessage(self,
                                         userID: str,
                                         replace: str,
                                         message: NotificationMsgSchema):
        # NotificationMessage和SystemMessage的区别是前者会存入数据库中而后者不会
        # 用户离线时的NotificationMessage上线后依旧能收到，SystemMessage只管发不管用户收没收到
        collection = DB_CRUD(Database.NotificationDB.value, userID, NotificationMsgSchema)
        collection.add(message.model_dump())

        sysMessage = SysMessageSchema(
            time=message.time,
            type=message.type,
            subType=message.subType,
            payload=message.payload.format(replace),
        )
        await self.sendingSystemMessage(userID, sysMessage)

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
        if userID not in self._userGroups or groupID not in self._userGroups[userID]:
            return

        check = beforeSendingCheck(userID, groupID, message)
        modify = beforeSendingModify(userID, groupID, message)
        result = check and modify
        if not result:
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type=SystemMessageType.FAIL.value,
                payload=result.value
            )
            await WCM.sendingSystemMessage(userID, sysMsg)
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
