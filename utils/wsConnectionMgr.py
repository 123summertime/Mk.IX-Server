from utils.dbCRUD import DB_CRUD

DB = "UserInfo"
GRP = "Group"
MSG = "OfflineMsg"



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

        DB_CRUD(DB, MSG).query({
            "uuid": userID,
            "group": self.groupID
        })

        # if userID in self._offlineMessage:
        #     for message in self._offlineMessage[userID]:
        #         await websocket.send_json(dict(message))
        #     del self._offlineMessage[userID]

        self._onlineUsers.add(userID)
        self._connections.add(websocket)

    def disconnect(self, websocket, userID):
        self._onlineUsers.remove(userID)
        self._connections.remove(websocket)

    async def sending(self, message, userID):
        offlineUsers = self._allUsers - self._onlineUsers
        for user in offlineUsers:
            offlineMsg = DB_CRUD(DB, MSG).add({
                "uuid": user,
                "group": self.groupID,
                "time": message.time,
                "type": message.type,
                "sender": message.sender,
                "payload": message.payload,
            })
            # if user in self._offlineMessage:
            #     self._offlineMessage[user].append(message)
            # else:
            #     self._offlineMessage[user] = [message]

        for websocket in self._connections:
            await websocket.send_json(dict(message))
