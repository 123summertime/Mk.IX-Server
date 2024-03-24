from const import Database, Collection
from utils.dbCRUD import DB_CRUD
from utils.helper import timestamp, beforeSendCheck
from schema.storage import StorageSchema
from schema.message import GetMessageSchema, SendMessageSchema


class ConnectionManager:
    def __init__(self):
        self.online = dict()

    def addConnectedGroup(self, groupID):
        if groupID not in self.online:
            exist = Collection.COLL_GRP.value.query(
                {"group": groupID},
                {"_id": 1}
            )

            if not exist:
                raise RuntimeError("Invalid group")

            self.online[groupID] = GroupConnections(groupID)

    def removeGroup(self, groupID):
        del self.online[groupID]


class GroupConnections:
    def __init__(self, groupID):
        self.groupID = groupID
        self._connections = dict() # item -> {groupID: wsConnection}
        self._currentGroupCollection = DB_CRUD(Database.StorageDB.value, self.groupID)

    def __repr__(self):
        return f"{self.groupID}:\n" \
               f"Online Users {self._connections}\n"

    async def connect(self, websocket, userID):
        await websocket.accept()

        lastSeen = Collection.COLL_ACC.value.query(
            {"uuid": userID},
            {"lastSeen": 1}
        )["lastSeen"]

        messages = self._currentGroupCollection.query(
            {"time": {"$gt": lastSeen}},
            {"_id": 0},
            True
        )

        for msg in messages:
            await websocket.send_json(dict(SendMessageSchema(
                time=msg["time"],
                type=msg["type"],
                group=self.groupID,
                senderID=msg["senderID"],
                senderKey=msg["senderKey"],
                payload=msg["payload"],
            )))

        self._connections[userID] = websocket

    def disconnect(self, userID):
        Collection.COLL_ACC.value.update(
            {"uuid": userID},
            {"$set": {"lastSeen": timestamp()}},
        )

        del self._connections[userID]

    async def sending(self, websocket, userID, message):
        check = beforeSendCheck(userID, self.groupID, message)
        if check != "OK":
            errorMsg = SendMessageSchema(
                time="-1",
                type="error",
                group="-1",
                senderID="-1",
                senderKey="-1",
                payload=check,
            )
            await websocket.send_json(dict(errorMsg))
            return

        userInfo = Collection.COLL_ACC.value.query(
            {"uuid": message.senderID},
            {"_id": 0, "lastUpdate": 1}
        )

        self._currentGroupCollection.add(dict(StorageSchema(
            time=message.time,
            type=message.type,
            senderID=message.senderID,
            senderKey=userInfo["lastUpdate"],
            payload=message.payload,
        )))

        sendMessage = SendMessageSchema(
            time=message.time,
            type=message.type,
            group=self.groupID,
            senderID=message.senderID,
            senderKey=userInfo["lastUpdate"],
            payload=message.payload,
        )

        for ws in self._connections.values():
            await ws.send_json(dict(sendMessage))


CM = ConnectionManager()
