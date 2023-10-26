from utils.dbCRUD import DB_CRUD
from schema.message import MessageSchema, OfflineMessageSchema

DB = "UserInfo"
GRP = "Group"
REF = "OfflineRef"
STO = "OfflineStorage"

COLLECTION_GRP = DB_CRUD(DB, GRP)

class ConnectionManager:
    def __init__(self):
        self.online = {}

    def addConnectedGroup(self, groupID):
        if groupID not in self.online:
            allUsers = set(DB_CRUD(DB, GRP).query(
                {"group": groupID},
                {"_id": 0, "user": 1}
            )['user'])
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

        offlineMsg = DB_CRUD(DB, REF).query({
            "uuid": userID,
            "group": self.groupID
        }, {
            "_id": 0,
            "uuid": 0,
            "group": 0
        }, True)
        print(offlineMsg)
        if offlineMsg:
            for message in offlineMsg:
                await websocket.send_json(dict(MessageSchema(
                    time=message["time"],
                    type=message["type"],
                    sender=message["sender"],
                    payload=message["payload"],
                )))
            DB_CRUD(DB, REF).delete({
                "uuid": userID,
                "group": self.groupID
            }, True)

        self._onlineUsers.add(userID)
        self._connections.add(websocket)

    def disconnect(self, websocket, userID):
        self._onlineUsers.remove(userID)
        self._connections.remove(websocket)

    async def sending(self, message, userID):
        offlineUsers = self._allUsers - self._onlineUsers
        for user in offlineUsers:
            offlineMsg = DB_CRUD(DB, REF).add(dict(OfflineMessageSchema(
                uuid = user,
                group = self.groupID,
                time = message.time,
                type = message.type,
                sender = message.sender,
                payload = message.payload
            )))


        for websocket in self._connections:
            await websocket.send_json(dict(message))
