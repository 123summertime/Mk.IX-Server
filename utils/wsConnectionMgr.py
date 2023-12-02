from const import Collection
from schema.storage import StorageSchema
from schema.message import GetMessageSchema, SendMessageSchema, OfflineMessageSchema


class ConnectionManager:
    def __init__(self):
        self.online = {}

    def addConnectedGroup(self, groupID):
        if groupID not in self.online:
            allUsers = Collection.COLL_GRP.value.query(
                {"group": groupID},
                {"_id": 0, "user": 1}
            )

            if not allUsers:
                raise RuntimeError("Invalid group")

            userIDs = set()
            for objID in allUsers["user"]:
                uuid = Collection.COLL_ACC.value.query(
                    {"_id": objID},
                    {"_id": 0, "uuid": 1}
                )["uuid"]
                userIDs.add(uuid)

            self.online[groupID] = GroupConnections(groupID, userIDs)


class GroupConnections:
    def __init__(self, groupID, allUsers):
        self.groupID = groupID
        self._connections = set()
        self._onlineUsers = set()
        self._allUsers = allUsers
        self._offlineMessage = dict()

    async def connect(self, websocket, userID):
        await websocket.accept()

        # 获取离线消息
        messageID = Collection.COLL_REF.value.query(
            {"uuid": userID, "group": self.groupID},
            {"refTo": 1},
            True
        )

        if messageID:
            # 对每条消息获取其消息引用(refTo) 发送后该消息的引用-1(refTimes) 为0时删除该消息
            for message in messageID:
                refTo = message["refTo"]
                storageMsg = Collection.COLL_STO.value.query(
                    {"_id": refTo},
                    {"_id": 0}
                )

                await websocket.send_json(dict(SendMessageSchema(
                    time=storageMsg["time"],
                    type=storageMsg["type"],
                    group=self.groupID,
                    senderID=storageMsg["senderID"],
                    senderKey=storageMsg["senderKey"],
                    payload=storageMsg["payload"],
                )))

                Collection.COLL_REF.value.delete(
                    {"refTo": refTo}
                )
                if storageMsg["refTimes"] == 1:
                    Collection.COLL_STO.value.delete(
                        {"_id": refTo},
                    )
                else:
                    Collection.COLL_STO.value.update(
                        {"_id": refTo},
                        {"$inc": {"refTimes": -1}}
                    )

        self._onlineUsers.add(userID)
        self._connections.add(websocket)

    def disconnect(self, websocket, userID):
        self._onlineUsers.remove(userID)
        self._connections.remove(websocket)

    async def sending(self, message):
        offlineUsers = self._allUsers - self._onlineUsers

        userInfo = Collection.COLL_ACC.value.query(
            {"uuid": message.senderID},
            {"_id": 0, "lastUpdate": 1}
        )

        if offlineUsers:
            msgObjID = Collection.COLL_STO.value.add(dict(StorageSchema(
                refTimes=len(offlineUsers),
                time=message.time,
                type=message.type,
                senderID=message.senderID,
                senderKey=userInfo["lastUpdate"],
                payload=message.payload,
            )))

            for user in offlineUsers:
                Collection.COLL_REF.value.add(dict(OfflineMessageSchema(
                    uuid=user,
                    group=self.groupID,
                    refTo=msgObjID.inserted_id,
                )))

        sendMessage = SendMessageSchema(
            time=message.time,
            type=message.type,
            group=self.groupID,
            senderID=message.senderID,
            senderKey=userInfo["lastUpdate"],
            payload=message.payload,
        )

        for websocket in self._connections:
            await websocket.send_json(dict(sendMessage))
