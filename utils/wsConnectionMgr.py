from const import Database, Collection
from utils.dbCRUD import DB_CRUD
from utils.helper import timestamp, beforeSendCheck
from schema.storage import StorageSchema
from schema.message import GetMessageSchema, SendMessageSchema, SysMessageSchema


class GroupConnectionManager:
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

    def removeSomeoneInGroup(self, groupID, uuid):
        self.online[groupID].disconnect(uuid)


class GroupConnections:
    def __init__(self, groupID):
        self.groupID = groupID
        self._connections = dict() # item -> {userID: wsConnection}
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
            sysMsg = SysMessageSchema(
                time=timestamp(),
                type="fail",
                payload=check
            )
            await SCM.sending(userID, sysMsg)
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


class SystemConnectionManager:
    def __init__(self):
        self._connections = dict() # item -> {userID: wsConnection}

    def __contains__(self, uuid):
        return uuid in self._connections

    async def connect(self, websocket, userID):
        await websocket.accept()
        self._connections[userID] = websocket

    def disconnect(self, userID):
        del self._connections[userID]

    async def sending(self, userID, payload):
        ws = self._connections[userID]
        await ws.send_json(dict(payload))


GCM = GroupConnectionManager()
SCM = SystemConnectionManager()
