from uuid import uuid4

from const import Collection
from schema.storage import StorageSchema
from schema.message import MessageSchema, OfflineMessageSchema


class ConnectionManager:
    def __init__(self):
        self.online = {}

    def addConnectedGroup(self, groupID):
        if groupID not in self.online:
            allUsers = Collection.COLL_GRP.value.query(
                {"group": groupID},
                {"_id": 0, "user": 1}
            )
            if "user" not in allUsers:
                raise RuntimeError("Invalid group")

            allUsers = set(allUsers["user"].keys())
            self.online[groupID] = GroupConnections(groupID, allUsers)


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
            {"_id": 0, "uuid": 0},
            True
        )

        if messageID:
            # 对每条消息获取其消息引用(refTo) 发送后该消息的引用-1(refTimes) 为0时删除该消息
            for message in messageID:
                refTo = message["refTo"]
                storageMsg = Collection.COLL_STO.value.query(
                    {"messageID": refTo},
                    {"_id": 0, "messageID": 0}
                )

                await websocket.send_json(dict(MessageSchema(
                    time=storageMsg["time"],
                    type=storageMsg["type"],
                    group=message["group"],
                    sender=storageMsg["sender"],
                    senderName=storageMsg["senderName"],
                    payload=storageMsg["payload"],
                )))

                Collection.COLL_REF.value.delete(
                    {"refTo": refTo}
                )
                if storageMsg["refTimes"] == 1:
                    Collection.COLL_STO.value.delete(
                        {"messageID": refTo},
                    )
                else:
                    Collection.COLL_STO.value.update(
                        {"messageID": refTo},
                        {"$inc": {"refTimes": -1}}
                    )

        self._onlineUsers.add(userID)
        self._connections.add(websocket)

    def disconnect(self, websocket, userID):
        self._onlineUsers.remove(userID)
        self._connections.remove(websocket)

    async def sending(self, message, userID):
        offlineUsers = self._allUsers - self._onlineUsers

        messageID = uuid4().hex
        Collection.COLL_STO.value.add(dict(StorageSchema(
            messageID=messageID,
            refTimes=len(offlineUsers),
            time=message.time,
            type=message.type,
            sender=message.sender,
            senderName=message.senderName,
            payload=message.payload,
        )))

        for user in offlineUsers:
            Collection.COLL_REF.value.add(dict(OfflineMessageSchema(
                uuid=user,
                group=self.groupID,
                refTo=messageID,
            )))

        for websocket in self._connections:
            await websocket.send_json(dict(message))
