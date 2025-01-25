import asyncio
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse

from depends import CheckRequest, RequestValidate, getSelfInfo, getUserInfo, checker, getUserInfoWithAvatar, OutputFileValidate
from public import API, Default, Database, Limits, RequestState, SystemMessageType, NotificationMsgSubtype
from schema import GroupSchema, Info, UserRegister, Reason, Avatar, Username, Bio, Password, UserSchema, \
    SysMessageSchema, MessagePayload, BroadcastMessageSchema, RequestMsgSchema, WebsocketTokenSchema, \
    NotificationMsgSchema, GetMessageSchema, InputValidate, FileInput, FileStorageSchema, BroadcastMeta
from utils import rateLimit, ACCOUNT, GROUP, FRIEND_REQUEST, WS_TOKEN, CrudHelpers, hashPassword, timestamp, \
    createAccessToken, getVirtualGroupID, WCM, FS

userRouter = APIRouter(prefix=f"/{API.VERSION.value}/user", tags=['User'])


@userRouter.post('/register')
@rateLimit(5, 60)
async def register(request: Request,
                   userRegister: UserRegister):
    '''
    用户注册
    '''
    username, password = userRegister.name, userRegister.password
    hashedPassword = hashPassword(password)
    time = timestamp()

    userID = str(uuid4().int)[::4]
    userInfo = UserSchema(
        uuid=userID,
        username=username,
        password=hashedPassword,
        avatar=Default.DEFAULT_AVATAR.value,
        bio=Default.DEFAULT_BIO.value,
        lastSeen={},
        lastUpdate=time,
        groups=[],
    ).model_dump(exclude={"id"})
    userObjID = ACCOUNT.add(userInfo).inserted_id

    # 注册就送文件传输助手群
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name="文件传输助手",
        avatar=Default.DEFAULT_AVATAR.value,
        lastUpdate=time,
        owner=userObjID,
        question={},
        admin=[],
        user=[userObjID],
    ).model_dump(exclude={"id"})

    groupObjID = GROUP.add(newGroup).inserted_id
    ACCOUNT.update(
        {"uuid": userID},
        {"$push": {"groups": groupObjID}}
    )
    Database.CLIENT.value[Database.STORAGE_DB.value][groupID].create_index([('time', 1)], unique=True)

    API.LOGGER.value.info(f"用户 {userID} 已注册")

    return {"uuid": userID}


@userRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends(),
          isBot: bool = Query(...)):
    '''
    登录表单验证
    formData: 表单
    '''
    userInfo = ACCOUNT.query(
        {"uuid": formData.username},
        {"password": 1}
    )

    if not userInfo:
        raise HTTPException(status_code=400, detail="用户不存在")

    hashedPassword = hashPassword(formData.password)
    if hashedPassword != userInfo.password:
        raise HTTPException(status_code=401, detail="密码不正确")

    token = createAccessToken(formData.username, isBot)

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@userRouter.get('/check')
def check(newToken=Depends(checker)):
    '''
    验证token是否有效
    :return: token
    '''
    return newToken


@userRouter.get('/wsToken')
@rateLimit(30, 30)
async def getWSToken(device: str = Query(...),
                     userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取websocket连接凭证
    websocket连接必须带上这个wsToken才允许连接，wsToken有效期很短
    '''
    # 没有deviceId就生成一个
    deviceID = device if device else str(uuid4().hex)[::4]
    time = timestamp()
    deviceInfo = userInfo.lastSeen

    if deviceID not in deviceInfo:
        msg = NotificationMsgSchema(
            time=time,
            subType=NotificationMsgSubtype.NEUTRAL.value,
            isGroupMessage=False,
            target=userInfo.uuid,
            payload=f"在新设备上登录(设备ID: {deviceID})",
            meta=BroadcastMeta(
                operation="new_device",
            )
        )
        asyncio.create_task(WCM.sendingNotificationMessage(userInfo.uuid, "", msg))

    # 历史登录设备已满，淘汰最久没有使用的设备
    if len(deviceInfo) == Limits.MAX_DEVICE.value:
        deviceInfo = {i: deviceInfo[i] for i in deviceInfo if deviceInfo[i] != min(deviceInfo.values())}

    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"lastSeen": deviceInfo}}
    )

    token = uuid4().hex
    info = WebsocketTokenSchema(
        time=time,
        uuid=userInfo.uuid,
        token=token,
        device=deviceID,
    )
    WS_TOKEN.add(info.model_dump())

    return {
        "device": deviceID,
        "token": token,
    }


@userRouter.get('/limits')
@rateLimit(30, 30)
async def getLimits(request: Request):
    def convert(limit, unit):
        if isinstance(limit, dict):
            return f"最低:{limit['MIN']}{unit} 最高:{limit['MAX']}{unit}"
        return f"{limit}{unit}"

    info = {
        "文本字数": convert(Limits.GROUP_TEXT_LENGTH_RANGE.value, ""),
        "图片大小": convert(Limits.GROUP_IMAGE_SIZE_RANGE.value, "KB"),
        "语音时长": convert(Limits.GROUP_AUDIO_LENGTH_RANGE.value, "秒"),
        "文件大小": convert(Limits.GROUP_FILE_SIZE_RANGE.value, "KB"),
        "群验证/好友申请有效期": convert(Limits.REQUEST_EXPIRE_MINUTES.value, "分钟"),
        "群消息/文件过期时间": convert(Limits.REQUEST_EXPIRE_MINUTES.value, "分钟"),
    }

    return info


@userRouter.get('/profile/me')
async def profile(userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取自己的信息 需要登录
    不包括avatar和password  avatar通过GET {uuid}/profile获取
    '''
    for index, groupObjID in enumerate(userInfo.groups):
        groupInfo = GROUP.query(
            {"_id": groupObjID},
            {"_id": 0, "group": 1, "lastUpdate": 1, "owner": 1, "admin": 1}
        ).model_dump(include={"group", "lastUpdate", "owner", "admin"})
        groupInfo["owner"] = CrudHelpers.userObjectIDtoInfo(groupInfo["owner"]).model_dump(include={"uuid", "lastUpdate"})
        groupInfo["admin"] = [CrudHelpers.userObjectIDtoInfo(i).model_dump(include={"uuid", "lastUpdate"}) for i in groupInfo["admin"]]
        userInfo.groups[index] = groupInfo

    for index, friendObjID in enumerate(userInfo.friends):
        userInfo.friends[index] = CrudHelpers.userObjectIDtoInfo(friendObjID).model_dump(include={"uuid", "lastUpdate"})

    info = userInfo.model_dump(include={"uuid", "username", "bio", "lastUpdate", "groups", "friends"})

    return info


@userRouter.get('/{uuid}/profile')
@rateLimit(30, 30)
async def userInfo(userInfo: UserSchema = Depends(getUserInfoWithAvatar)):
    '''
    获取用户信息
    :return: 用户的username, avatar, lastUpdate
    '''
    info = {
        "username": userInfo.username,
        "avatar": userInfo.avatar,
        "lastUpdate": userInfo.lastUpdate,
    }
    return info


@userRouter.get('/{uuid}/profile/current')
@rateLimit(30, 30)
async def getUserCurrentInfo(userInfo: UserSchema = Depends(getUserInfo)):
    '''
    获取用户当前信息
    :return: 用户的lastSeen, bio
    '''
    info = {
        "bio": userInfo.bio,
        "lastSeen": "在线" if userInfo.uuid in WCM else max(userInfo.lastSeen.values()),
        "lastUpdate": userInfo.lastUpdate,
    }
    return info


@userRouter.patch('/{uuid}/profile/avatar')
@rateLimit(5, 30)
async def modifyUserAvatar(newAvatar: Avatar,
                           userInfo: UserSchema = Depends(getSelfInfo)):
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"avatar": newAvatar.avatar, "lastUpdate": timestamp()}}
    )

    return {"detail": "ok"}


@userRouter.patch('/{uuid}/profile/username')
@rateLimit(10, 30)
async def modifyUsername(newName: Username,
                         userInfo: UserSchema = Depends(getSelfInfo)):
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"username": newName.name, "lastUpdate": timestamp()}}
    )

    return {"detail": "ok"}


@userRouter.patch('/{uuid}/profile/bio')
@rateLimit(10, 30)
async def modifyUserBio(bio: Bio,
                        userInfo: UserSchema = Depends(getSelfInfo)):
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"bio": bio.bio}}
    )

    return {"detail": "ok"}


@userRouter.patch('/{uuid}/profile/password')
@rateLimit(10, 30)
async def modifyUserPassword(newPassword: Password,
                             userInfo: UserSchema = Depends(getSelfInfo)):
    hashed = hashPassword(newPassword.password)
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"password": hashed}}
    )

    return {"detail": "ok"}


@userRouter.delete('/{uuid}')
@rateLimit(10, 30)
async def deleteFriend(userInfo: UserSchema = Depends(getSelfInfo),
                       targetInfo: UserSchema = Depends(getUserInfo)):
    if userInfo.id == targetInfo.id \
            or targetInfo.id not in userInfo.friends \
            or userInfo.id not in targetInfo.friends:
        raise HTTPException(status_code=403)

    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$pull": {"friends": targetInfo.id}},
    )
    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$pull": {"friends": userInfo.id}},
    )

    removeMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=targetInfo.uuid,
        groupType="friend",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"已解除好友关系",
            meta=BroadcastMeta(
                operation="friend_remove",
            )
        )
    )
    await WCM.sendingGroupMessage(userInfo.uuid, removeMessage)

    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.NEGATIVE.value,
        isGroupMessage=False,
        target=targetInfo.uuid,
        blank=userInfo.uuid,
        payload='您已不在{}的好友列表中',
        meta=BroadcastMeta(
            operation="friend_remove",
            var={
                "id": userInfo.uuid,
                "type": "user",
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, userInfo.username, notificationMessage))

    virtualGroupID = getVirtualGroupID(userInfo, targetInfo)
    WCM.disconnectUserFromGroup(userInfo.uuid, virtualGroupID)
    WCM.disconnectUserFromGroup(targetInfo.uuid, virtualGroupID)

    return {"detail": "ok"}


@userRouter.post('/{uuid}/verify/request')
@rateLimit(10, 30)
async def friendRequest(reason: Reason,
                        info: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), uuid=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=False,
                                uuid=uuid,
                                checkers=[
                                    RequestValidate.notExist,
                                    RequestValidate.notSelf,
                                    RequestValidate.notFriend,
                                ],
                            )()
                        )):
    '''
    发送加好友请求
    '''
    time = timestamp()
    userInfo, targetInfo = info.userInfo, info.targetInfo

    # 推送给接收方
    sysMessage = SysMessageSchema(
        time=time,
        type=SystemMessageType.FRIEND.value,
        target=targetInfo.uuid,
        targetKey=targetInfo.lastUpdate,
        state=RequestState.PENDING.value,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.reason,
    )
    asyncio.create_task(WCM.sendingSystemMessage(targetInfo.uuid, sysMessage))

    requestMessage = RequestMsgSchema(
        time=time,
        type=SystemMessageType.FRIEND.value,
        target=targetInfo.uuid,
        senderID=userInfo.uuid,
        payload=reason.reason,
    )
    FRIEND_REQUEST.add(requestMessage.model_dump())

    return {"detail": "ok"}


@userRouter.get('/{uuid}/verify/request')
async def queryFriendRequest(device: str = Query(...),
                             userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取好友申请
    结果通过ws(WCM)发送
    '''
    time = timestamp()
    messages = FRIEND_REQUEST.queryMany(  # 获取在有效时间内的请求 单位:ms
        {"target": userInfo.uuid, "time": {"$gt": str(int(time) - Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000)}},
        {"_id": 0}
    )

    for msg in messages:
        senderInfo = ACCOUNT.query(
            {"uuid": msg.senderID},
            {"lastUpdate": 1},
        )
        sysMessage = SysMessageSchema(
            time=msg.time,
            type=msg.type,
            state=msg.state,
            target=msg.target,
            targetKey=userInfo.lastUpdate,
            senderID=msg.senderID,
            senderKey=senderInfo.lastUpdate,
            payload=msg.payload,
        )
        asyncio.create_task(WCM.sendingSystemMessage(userInfo.uuid, sysMessage, device=device))


@userRouter.post('/{uuid}/verify/request/{time}')
@rateLimit(30, 30)
async def requestAccept(time: str = Path(...),
                        info: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), uuid=Path(...), time=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=False,
                                uuid=uuid,
                                time=time,
                                checkers=[RequestValidate.exist],
                            )()
                        )):
    '''
    通过好友申请
    '''
    userInfo, targetInfo, requestInfo = info.userInfo, info.targetInfo, info.requestInfo
    currentTime = timestamp()
    currentState = RequestState.ACCEPTED.value
    groupID = getVirtualGroupID(userInfo, targetInfo)

    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$push": {"friends": userInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"friends": targetInfo.id}}
    )
    FRIEND_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )
    Database.CLIENT.value[Database.STORAGE_DB.value][groupID].create_index([('time', 1)], unique=True)

    WCM.userJoinedGroup(requestInfo.senderID, groupID, "friend")
    WCM.userJoinedGroup(requestInfo.target, groupID, "friend")

    # 向发起方推送加好友成功的通知
    notificationMessage = NotificationMsgSchema(
        time=currentTime,
        subType=NotificationMsgSubtype.POSITIVE.value,
        isGroupMessage=False,
        target=requestInfo.senderID,
        blank=requestInfo.target,
        payload='{}已通过你的好友申请',
        meta=BroadcastMeta(
            operation="friend_request_accepted",
            var={
                "id": requestInfo.target,
                "type": "user",
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(requestInfo.senderID, userInfo.username, notificationMessage))

    # 向双方推送加好友成功的消息
    sysMessage = SysMessageSchema(
        time=currentTime,
        type=SystemMessageType.FRIENDED.value,
        target=targetInfo.uuid,
        targetKey=targetInfo.lastUpdate,
        state=currentState,
        payload="",
    )
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)
    sysMessage.target = userInfo.uuid
    sysMessage.targetKey = userInfo.lastUpdate
    await WCM.sendingSystemMessage(requestInfo.senderID, sysMessage)

    # 更新申请结果
    sysMessage = SysMessageSchema(
        time=requestInfo.time,
        type=requestInfo.type,
        target=userInfo.uuid,
        targetKey=userInfo.lastUpdate,
        state=currentState,
        senderID=targetInfo.uuid,
        senderKey=targetInfo.lastUpdate,
        payload=requestInfo.payload
    )
    asyncio.create_task(WCM.sendingSystemMessage(requestInfo.target, sysMessage))

    # 在群里发送系统消息
    joinedMessage = BroadcastMessageSchema(
        time=currentTime,
        type="system",
        group=targetInfo.uuid,
        groupType="friend",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content="我们已经是好友了，一起来聊天吧！",
            meta=BroadcastMeta(
                operation="friended",
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, joinedMessage))

    return {"detail": "ok"}


@userRouter.delete('/{uuid}/verify/request/{time}')
@rateLimit(30, 30)
async def requestReject(time: str = Path(...),
                        info: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), uuid=Path(...), time=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=False,
                                uuid=uuid,
                                time=time,
                                checkers=[RequestValidate.exist],
                            )()
                        )):
    userInfo, targetInfo, requestInfo = info.userInfo, info.targetInfo, info.requestInfo
    currentState = RequestState.REJECTED.value

    FRIEND_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

    # 向发起方推送加好友失败的消息
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.NEGATIVE.value,
        isGroupMessage=False,
        target=requestInfo.senderID,
        blank=requestInfo.target,
        payload='{}已拒绝你的好友申请',
        meta=BroadcastMeta(
            operation="friend_request_rejected",
            var={
                "id": requestInfo.target,
                "type": "user",
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(requestInfo.senderID, userInfo.username, notificationMessage))

    # 更新申请结果
    sysMessage = SysMessageSchema(
        time=requestInfo.time,
        type=requestInfo.type,
        target=userInfo.uuid,
        targetKey=userInfo.lastUpdate,
        state=currentState,
        senderID=targetInfo.uuid,
        senderKey=targetInfo.lastUpdate,
        payload=requestInfo.payload
    )
    asyncio.create_task(WCM.sendingSystemMessage(requestInfo.target, sysMessage))

    return {"detail": "ok"}


@userRouter.post('/{uuid}/upload')
@rateLimit(10, 30)
async def groupFileUpload(userInfo: UserSchema = Depends(getSelfInfo),
                          targetInfo: UserSchema = Depends(getUserInfo),
                          fileInput: FileInput = Depends(InputValidate.validateInputFile)):
    '''
    好友上传文件
    '''
    if userInfo.id not in targetInfo.friends or targetInfo.id not in userInfo.friends:
        raise HTTPException(status_code=403, detail="非好友之间禁止发送信息")

    time = timestamp()
    groupID = getVirtualGroupID(userInfo, targetInfo)
    fileName, fileType, content = fileInput.fileName, fileInput.fileType, fileInput.content
    hashcode = FS.add(content, fileName, fileType, groupID)

    message = GetMessageSchema(
        time=time,
        type=fileType,
        group=targetInfo.uuid,
        groupType="friend",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            name=fileName,
            size=len(content),
            content=hashcode,
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, message))

    API.LOGGER.value.info(f"{userInfo.uuid} 在 {targetInfo.uuid}(friend) 发送了 {fileType} 类型的消息({time})")
    return {"time": time}


@userRouter.get('/{uuid}/download/{hashcode}')
@rateLimit(10, 30)
async def downloadFile(userInfo: UserSchema = Depends(getSelfInfo),
                       targetInfo: UserSchema = Depends(getUserInfo),
                       file: FileStorageSchema = Depends(OutputFileValidate.existsFriend)):
    if userInfo.id not in targetInfo.friends or targetInfo.id not in userInfo.friends:
        raise HTTPException(status_code=403, detail="非好友之间禁止发送信息")

    READ_SIZE = 1024 * 1024  # 1MB

    def iter():
        while chunk := file.file.read(READ_SIZE):
            yield chunk
            
    res = StreamingResponse(iter(), media_type=file.type)
    res.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(file.name)}"
    res.headers["Content-Length"] = str(file.file.length)
    return res
