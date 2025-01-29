import json
import asyncio
from typing import Optional
from functools import lru_cache
from collections import defaultdict

from fastapi import WebSocket

from public import Database, Limits, SystemMessageType, API
from schema import GetMessageSchema, SendMessageSchema, SysMessageSchema, StorageSchema, NotificationMsgSchema, BroadcastMeta
from .rateLimit import rateLimit
from .checker import beforeSendingCheck
from .modifier import beforeSendingModify
from .crud import DB_CRUD, ACCOUNT, GROUP, CrudHelpers
from .helper import timestamp, getVirtualGroupID, getTargetFromVirtualGroupID


class GroupItem:
    def __init__(self, groupID: str, type_: str):
        self.groupID = groupID
        self._collection = DB_CRUD(Database.STORAGE_DB.value, groupID, StorageSchema)
        self._userInGroup = set()
        self._type = type_

        banList = GROUP.query(
            {"group": groupID},
            {"ban": 1}
        )
        self._ban = banList.ban if banList else dict()

    def __repr__(self):
        return f"{self.groupID}({self._type}) -> {str(self._userInGroup)}"

    def addUser(self, userID):
        self._userInGroup.add(userID)

    def removeUser(self, userID):
        self._userInGroup.discard(userID)

    def setBan(self, userID, endTime):
        self._ban[userID] = endTime

    def isBan(self, userID) -> tuple[bool, str]:
        if userID not in self._ban or timestamp() >= self._ban[userID]:
            return True, ""
        return False, self._ban[userID]

    @property
    def getType(self):
        return self._type

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
        userID ───> deviceID ───> websocket
           └──────> groupID ────> groupItem
        '''

    def __contains__(self, userID):
        return userID in self._users

    def __repr__(self):
        return f"User: {self._users}\n " \
               f"Device: {self._device.keys()}\n " \
               f"Group: {self._groups}\n" \
               f"UserGroup: {self._userGroups}\n" \


    def updateGroupBan(self, groupID: str, userID: str, endTime: str):
        if groupID not in self._groups:
            self._groups[groupID] = GroupItem(groupID, "group")
        self._groups[groupID].setBan(userID, endTime)

    def getGroupBan(self, groupID: str, userID: str):
        return self._groups[groupID].isBan(userID)

    def userJoinedGroup(self, userID: str, groupID: str, type_: str):
        if userID in self._users:
            self._userGroups[userID].add(groupID)
            self._userConnectToGroupItem(userID, groupID, type_)

    def _userConnectToGroupItem(self, userID: str, groupID: str, type_: str):
        if groupID not in self._groups:
            self._groups[groupID] = GroupItem(groupID, type_)
        self._groups[groupID].addUser(userID)
        self._userGroups[userID].add(groupID)

    async def popDevice(self, userID: str):
        ''' 该用户到达最大在线数量，随机pop一台设备 '''
        if len(self._users[userID]) >= Limits.MAX_ONLINE_DEVICE.value:
            device = list(self._users[userID])[0]
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type=SystemMessageType.LOGOUT.value,
                payload=f"已达到最大同时在线设备数({Limits.MAX_ONLINE_DEVICE.value}台)，请尝试重新登录"
            ).model_dump()
            asyncio.create_task(self._device[device].send_json(sysMsg))

            try:
                ws = self._device[device]
                await ws.close()
                self._device.pop(device, "")
            except Exception:
                pass

    async def connect(self,
                      userID: str,
                      deviceID: str,
                      websocket: WebSocket,
                      Sec_Websocket_Protocol: str,
                      Authorization: str):

        await self.popDevice(userID)
        self._users[userID].add(deviceID)
        self._device[deviceID] = websocket

        if Authorization:
            await websocket.accept()
        else:
            await websocket.accept(subprotocol=Sec_Websocket_Protocol)

        userInfo = ACCOUNT.query(
            {"uuid": userID},
            {"groups": 1, "friends": 1, "lastSeen": 1},
        )

        groupIDs = list(map(lambda i: CrudHelpers.groupObjectIDtoInfo(i).group, userInfo.groups))
        friends = map(lambda i: CrudHelpers.userObjectIDtoInfo(i).uuid, userInfo.friends)
        friendVirtualGroupIDs = list(map(lambda i: getVirtualGroupID(userID, i), friends))
        for groupID in groupIDs:
            self._userConnectToGroupItem(userID, groupID, "group")
        for groupID in friendVirtualGroupIDs:
            self._userConnectToGroupItem(userID, groupID, "friend")

        lastSeen = userInfo.lastSeen.get(deviceID, str(int(timestamp()) - 3 * 24 * 60 * 60 * 1000))  # 新设备获取3天内的历史消息
        asyncio.create_task(self._postOfflineNotificationMessages(userID, lastSeen, websocket))
        asyncio.create_task(self._postOfflineGroupMessages(userID, groupIDs, lastSeen, websocket))
        asyncio.create_task(self._postOfflineGroupMessages(userID, friendVirtualGroupIDs, lastSeen, websocket))

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
            if msg.blank:
                targetInfo = (GROUP if msg.isGroupMessage else ACCOUNT).query(
                    {("group" if msg.isGroupMessage else "uuid"): msg.blank},
                    {("name" if msg.isGroupMessage else "username"): 1},
                )
                if not targetInfo:
                    name = ""
                else:
                    name = targetInfo.name if msg.isGroupMessage else targetInfo.username
                msg.payload = msg.payload.format(name)
                msg.meta.var["name"] = name

            m = SysMessageSchema(
                time=msg.time,
                type=msg.type,
                subType=msg.subType,
                payload=msg.payload,
                meta=msg.meta,
            )
            await websocket.send_json(m.model_dump())

    async def _postOfflineGroupMessages(self,
                                        userID: str,
                                        groupIDs: list,
                                        lastSeen: str,
                                        websocket: WebSocket):
        '''
        发送用户离线时收到的消息
        '''
        BATCH_SIZE = 100

        @lru_cache(maxsize=128)
        def getLastUpdate(account):
            return ACCOUNT.query(
                    {"uuid": account},
                    {"_id": 0, "lastUpdate": 1}
                ).lastUpdate

        for groupID in groupIDs:
            type_ = self._groups[groupID].getType
            messages = self._groups[groupID].collectionCRUD.queryMany(
                {"time": {"$gt": lastSeen}},
                {"_id": 0},
            )

            for i, msg in enumerate(messages):
                lastUpdate = getLastUpdate(msg.senderID)
                m = SendMessageSchema(
                    time=msg.time,
                    type=msg.type,
                    group=groupID if type_ == "group" else getTargetFromVirtualGroupID(groupID, userID),
                    senderID=msg.senderID,
                    senderKey=lastUpdate,
                    payload=msg.payload,
                )
                messages[i] = m.model_dump()

            for i in range(0, len(messages), BATCH_SIZE):
                await asyncio.gather(*[websocket.send_json(msg) for msg in messages[i:i+BATCH_SIZE]])
                await asyncio.sleep(0.001)

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
        except Exception:
            pass

        # 更新device的lastSeen
        ACCOUNT.update(
            {"uuid": userID},
            {"$set": {f"lastSeen.{deviceID}": timestamp()}}
        )

        # 清理工作
        self._users[userID].discard(deviceID)
        if not self._users[userID]:  # 用户所有设备都下线时
            for groupID in self._userGroups[userID]:
                self._groups[groupID].removeUser(userID)
                if self._groups[groupID].onlineUserCount == 0:
                    self._groups.pop(groupID)
            self._users.pop(userID)
            self._userGroups.pop(userID)
        self._device.pop(deviceID)

    def disconnectUserFromGroup(self,
                                userID: str,
                                groupID: str):
        groupItem = self._groups[groupID]
        groupItem.removeUser(userID)
        self._userGroups[userID].discard(groupID)

    def disconnectGroup(self, groupID):
        groupItem = self._groups[groupID]
        for userID in groupItem.onlineUserList:
            self._userGroups[userID].discard(groupID)
        self._groups.pop(groupID)

    async def sendingNotificationMessage(self,
                                         userID: str,
                                         replace: str,
                                         message: NotificationMsgSchema):
        # NotificationMessage和SystemMessage的区别是前者会存入数据库中而后者不会
        # 用户离线时的NotificationMessage上线后依旧能收到，SystemMessage只管发不管用户收没收到
        collection = DB_CRUD(Database.NotificationDB.value, userID, NotificationMsgSchema)
        collection.add(message.model_dump())

        message.meta.var["name"] = replace
        sysMessage = SysMessageSchema(
            time=message.time,
            type=message.type,
            subType=message.subType,
            payload=message.payload.format(replace),
            meta=message.meta
        )
        asyncio.create_task(self.sendingSystemMessage(userID, sysMessage))

    async def sendingSystemMessage(self,
                                   userID: str,
                                   message: SysMessageSchema,
                                   *,
                                   device: Optional[str] = None):
        post = message.model_dump()
        for d in self._users[userID]:
            if d == device or not device:
                ws = self._device[d]
                asyncio.create_task(ws.send_json(post))

    async def sendingEchoMessage(self,
                                 deviceID: str,
                                 message: SysMessageSchema):
        ws = self._device[deviceID]
        asyncio.create_task(ws.send_json(message.model_dump()))

    @rateLimit(Limits.MESSAGE_RATE.value, 1)
    async def sendingGroupMessage(self,
                                  userID: str,
                                  message: GetMessageSchema,
                                  device: Optional[str] = None):
        if message.groupType == "friend":
            message.group = getVirtualGroupID(userID, message.group)
        groupID = message.group
        if userID not in self._userGroups or groupID not in self._userGroups[userID]:
            return

        ok, detail = self.getGroupBan(groupID, userID)
        if not ok and message.type != "system":
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type=SystemMessageType.BAN.value,
                payload=detail,
            )
            asyncio.create_task(self.sendingSystemMessage(userID, sysMsg))
            return

        if message.type != "system":
            check = beforeSendingCheck(userID, groupID, message)
            modify = beforeSendingModify(userID, groupID, message) if check else check
            result = check and modify
            if not result:
                sysMsg = SysMessageSchema(
                    time=timestamp(),
                    type=SystemMessageType.FAIL.value,
                    payload=result.value
                )
                asyncio.create_task(self.sendingSystemMessage(userID, sysMsg))
                return

        userInfo = ACCOUNT.query(
            {"uuid": message.senderID},
            {"lastUpdate": 1}
        )

        sendMessage = SendMessageSchema(
            time=message.time,
            type=message.type,
            group=groupID,
            senderID=message.senderID,
            senderKey=userInfo.lastUpdate,
            payload=message.payload,
        )

        groupItem = self._groups[groupID]
        if groupItem.getType == "group":
            m = sendMessage.model_dump()
            for uuid in groupItem.onlineUserList:
                for d in self._users[uuid]:
                    ws = self._device[d]
                    asyncio.create_task(ws.send_json(m))
        else:
            for uuid in groupItem.onlineUserList:
                sendMessage.group = getTargetFromVirtualGroupID(groupID, uuid)
                m = sendMessage.model_dump()
                for d in self._users[uuid]:
                    ws = self._device[d]
                    asyncio.create_task(ws.send_json(m))

        API.LOGGER.value.debug(f"{groupID}: {sendMessage.model_dump()}")
        if device:
            # 返回发送的消息ID
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type=SystemMessageType.ECHO.value,
                payload=json.dumps({"time": message.time, "echo": message.echo})
            )
            asyncio.create_task(self.sendingSystemMessage(userID, sysMsg, device=device))

        if message.type != "revoke":
            storageMessage = StorageSchema(
                time=message.time,
                type=message.type,
                senderID=message.senderID,
                payload=message.payload,
            ).model_dump()

            groupItem.collectionCRUD.add(storageMessage)


WCM = WebsocketConnectionManager()
