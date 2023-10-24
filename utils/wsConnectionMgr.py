from utils import dbCRUD

DB = "UserInfo"
COLLECTION = "Group"


class ConnectionManager:
    def __init__(self):
        self.online = {}

    def addConnectedGroup(self, groupID):
        if groupID not in self.online:
            allUsers = set(dbCRUD.DB_CRUD(DB, COLLECTION).query(
                {"group": groupID},
                {"_id": 0, "user": 1}
            )['user'])
            self.online[groupID] = GroupConnections(allUsers)


class GroupConnections:
    def __init__(self, allUsers):
        self.connections = set()
        self.onlineUsers = set()
        self.allUsers = allUsers
        self.offlineMessage = dict()

    async def connect(self, websocket, userID):
        await websocket.accept()
        if userID in self.offlineMessage:
            for message in self.offlineMessage[userID]:
                await websocket.send_json(dict(message))
            del self.offlineMessage[userID]
        self.onlineUsers.add(userID)
        self.connections.add(websocket)

    def disconnect(self, websocket, userID):
        self.onlineUsers.remove(userID)
        self.connections.remove(websocket)

    async def sending(self, message, userID):
        offlineUsers = self.allUsers - self.onlineUsers
        for user in offlineUsers:
            if user in self.offlineMessage:
                self.offlineMessage[user].append(message)
            else:
                self.offlineMessage[user] = [message]
        for websocket in self.connections:
            await websocket.send_json(dict(message))
