from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.security import OAuth2PasswordRequestForm

from depends.checkPermission import CheckRequest, RequestValidate
from depends.getInfo import getSelfInfo, getUserInfo, checker, getUserInfoWithAvatar
from public.const import API, Auth, Default, Database, Limits
from public.stateCode import RequestState, SystemMessageType, NotificationMsgSubtype
from schema.group import GroupSchema
from schema.group import Info
from schema.input import UserRegister, Reason, Avatar, Username, Bio, Password
from schema.message import SysMessageSchema, MessagePayload, GetMessageSchema, BroadcastMessageSchema
from schema.storage import RequestMsgSchema, WebsocketTokenSchema, NotificationMsgSchema
from schema.user import UserSchema
from utils.rateLimit import rateLimit
from utils.crud import ACCOUNT, GROUP, DB_CRUD, FRIEND_REQUEST, WS_TOKEN, CrudHelpers
from utils.helper import hashPassword, timestamp, createAccessToken
from utils.wsConnectionMgr import WCM

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
    ).model_dump()
    del userInfo["id"]
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
    ).model_dump()
    del newGroup["id"]

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

    accessTokenExpires = timedelta(minutes=Auth.USER_ACCESS_TOKEN_EXPIRE_MINUTES.value)
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
        )
        await WCM.sendingNotificationMessage(userInfo.uuid, "", msg)

    # 历史登录设备已满，淘汰最久没有使用的设备
    if len(deviceInfo) == Limits.MAX_DEVICE.value:
        deviceInfo = {i: deviceInfo[i] for i in deviceInfo if deviceInfo[i] != min(deviceInfo.values())}
        deviceInfo[deviceID] = time

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
        ).model_dump()
        groupInfo["owner"] = CrudHelpers.userObjectIDtoInfo(groupInfo["owner"]).model_dump()
        groupInfo["admin"] = [CrudHelpers.userObjectIDtoInfo(i).model_dump() for i in groupInfo["admin"]]
        userInfo.groups[index] = groupInfo

    info = userInfo.model_dump()
    del info["id"]

    return info


@userRouter.get('/{uuid}/profile')
@rateLimit(30, 30)
async def userInfo(userInfo: UserSchema = Depends(getUserInfoWithAvatar)):
    '''
    获取用户信息
    :param uuid: 用户uuid
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
    :param uuid: 用户uuid
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


@userRouter.post('/{uuid}/verify/request')
@rateLimit(10, 30)
async def friendRequest(reason: Reason,
                        info: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), uuid=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=False,
                                uuid=uuid,
                                checkers=[RequestValidate.notExist, RequestValidate.notSelf],
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
    await WCM.sendingSystemMessage(targetInfo.uuid, sysMessage)

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
async def queryFriendRequest(userInfo: UserSchema = Depends(getSelfInfo)):
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
            {"_id": 0, "lastUpdate": 1},
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
        await WCM.sendingSystemMessage(userInfo.uuid, sysMessage)


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
    name = f"{targetInfo.username}和{userInfo.username}的群聊"
    currentState = RequestState.ACCEPTED.value
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Default.DEFAULT_AVATAR.value,
        lastUpdate=currentTime,
        owner=targetInfo.id,
        question={},
        admin=[userInfo.id],
        user=[targetInfo.id, userInfo.id],
    ).model_dump()
    del newGroup["id"]

    groupObjID = GROUP.add(newGroup).inserted_id
    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )
    FRIEND_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )
    Database.CLIENT.value[Database.STORAGE_DB.value][groupID].create_index([('time', 1)], unique=True)

    WCM.userJoinedGroup(requestInfo.senderID, groupID)
    WCM.userJoinedGroup(requestInfo.target, groupID)

    # 向发起方推送加好友成功的通知
    notificationMessage = NotificationMsgSchema(
        time=currentTime,
        subType=NotificationMsgSubtype.POSITIVE.value,
        isGroupMessage=False,
        target=requestInfo.senderID,
        blank=requestInfo.target,
        payload='"{}"已通过你的好友申请',
    )
    await WCM.sendingNotificationMessage(requestInfo.senderID, userInfo.username, notificationMessage)

    # 向双方推送加好友成功的消息
    sysMessage = SysMessageSchema(
        time=currentTime,
        type=SystemMessageType.FRIENDED.value,
        target=groupID,
        targetKey=time,
        state=currentState,
        payload="",
    )
    await WCM.sendingSystemMessage(requestInfo.senderID, sysMessage)
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)

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
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)

    # 在群里发送系统消息
    joinedMessage = BroadcastMessageSchema(
        time=currentTime,
        type=SystemMessageType.SYSTEM.value,
        group=groupID,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content="我们已经是好友了，一起来聊天吧！",
        )
    )
    await WCM.sendingGroupMessage(userInfo.uuid, groupID, joinedMessage)

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
        payload='"{}"已拒绝你的好友申请',
    )
    await WCM.sendingNotificationMessage(requestInfo.senderID, userInfo.username, notificationMessage)

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
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)

    return {"detail": "ok"}
