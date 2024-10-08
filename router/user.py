from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.security import OAuth2PasswordRequestForm

from depends.getInfo import getSelfInfo, getUserInfo, checker, getUserInfoWithAvatar
from depends.checkPermission import CheckRequest, RequestValidate
from public.const import API, Auth, Default, Database, Limits
from public.stateCode import RequestState
from schema.group import GroupSchema
from schema.input import UserRegister, Reason
from schema.message import SysMessageSchema, MessagePayload, GetMessageSchema
from schema.storage import RequestMsgSchema, WebsocketTokenSchema
from schema.group import Info
from schema.user import UserSchema
from utils.crud import ACCOUNT, GROUP, DB_CRUD, FRIEND_REQUEST, WS_TOKEN, CrudHelpers
from utils.helper import hashPassword, timestamp, createAccessToken
from utils.wsConnectionMgr import SCM, GCM, WCM

userRouter = APIRouter(prefix=f"/{API.VERSION.value}/user", tags=['User'])


@userRouter.post('/register')
def register(userRegister: UserRegister):
    '''
    用户注册
    '''
    userName, password = userRegister.name, userRegister.password
    hashedPassword = hashPassword(password)
    time = timestamp()

    userID = str(uuid4().int)[::4]
    userInfo = UserSchema(
        uuid=userID,
        userName=userName,
        password=hashedPassword,
        avatar=Default.DEFAULT_AVATAR.value,
        bio=Default.DEFAULT_BIO.value,
        lastSeen=time,
        lastUpdate=time,
        groups=[],
    ).model_dump()
    del userInfo["id"]
    ACCOUNT.add(userInfo)

    return {"uuid": userID}


@userRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends(),
          isBot: bool = False):
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
def getWSToken(device: str = Query(...),
               userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取websocket连接凭证
    websocket连接必须带上这个wsToken才允许连接，wsToken有效期很短
    '''
    # 没有deviceId就生成一个
    deviceID = device if device else str(uuid4().hex)[::4]
    time = timestamp()
    deviceInfo = userInfo.lastSeen

    # 历史登录设备已满，淘汰最久没有使用的设备
    if len(deviceInfo) == Limits.MAX_DEVICE.value:
        deviceInfo = {i: deviceInfo[i] for i in deviceInfo if deviceInfo[i] != min(deviceInfo.values())}
        deviceInfo[deviceID] = time

    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$set": {"lastSeen": deviceInfo}}
    )

    # TODO: 同时在线设备已满强制下线

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


@userRouter.get('/profile/me')
def profile(userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取自己的信息 需要登录
    不包括avatar和password  avatar通过GET profile/{uuid}获取
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
def userInfo(userInfo: UserSchema = Depends(getUserInfoWithAvatar)):
    '''
    获取用户信息
    :param uuid: 用户uuid
    :return: 用户的userName, avatar, lastUpdate
    '''
    info = {
        "username": userInfo.username,
        "avatar": userInfo.avatar,
        "lastUpdate": userInfo.lastUpdate,
    }

    return info


@userRouter.get('/{uuid}/profile/current')
def getUserCurrentInfo(userCurrentInfo: UserSchema = Depends(getUserInfo)):
    '''
    获取用户当前信息
    :param uuid: 用户uuid
    :return: 用户的lastSeen, bio
    '''
    if userCurrentInfo.uuid in WCM:
        userCurrentInfo.lastSeen = "在线"

    info = {
        "bio": userCurrentInfo.bio,
        "lastSeen": userCurrentInfo.lastSeen,
        "lastUpdate": userCurrentInfo.lastUpdate,
    }

    return info


@userRouter.post('/{uuid}/verify/request')
async def friendRequest(reason: Reason,
                        info: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), uuid=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=False,
                                uuid=uuid,
                                checkers=[RequestValidate.notExist],
                            )()
                        )):
    '''
    发送加好友请求
    '''
    time = timestamp()
    userInfo, targetInfo = info.userInfo, info.targetInfo

    sysMessage = SysMessageSchema(
        time=time,
        type="friend",
        target=targetInfo.uuid,
        targetKey=targetInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.reason,
    )
    # await SCM.sending(targetInfo.uuid, sysMessage)
    await WCM.sendingSystemMessage(targetInfo.uuid, sysMessage)

    requestMessage = RequestMsgSchema(
        time=time,
        type="friend",
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
    结果通过ws(SCM)发送
    '''
    time = timestamp()
    reqCollection = DB_CRUD(Database.REQUEST_DB.value, Database.FRIEND_REQUEST_COLLECTION.value, RequestMsgSchema)
    messages = reqCollection.queryMany(  # 获取在有效时间内的请求 单位:ms
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
        # await SCM.sending(userInfo.uuid, sysMessage)
        await WCM.sendingSystemMessage(userInfo.uuid, sysMessage)


@userRouter.post('/{uuid}/verify/request/{time}')
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
    name = f"{targetInfo.username}和{userInfo.username}的群聊"
    currentState = RequestState.ACCEPTED.value
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Default.DEFAULT_AVATAR.value,
        lastUpdate=timestamp(),
        owner=targetInfo.id,
        question={},
        admin=[],
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

    # 向双方推送加好友成功的消息
    sysMessage = SysMessageSchema(
        time=timestamp(),
        type="friended",
        target=groupID,
        state=currentState,
        payload=name
    )
    # await SCM.sending(requestInfo.senderID, sysMessage)
    # await SCM.sending(requestInfo.target, sysMessage)
    await WCM.sendingSystemMessage(requestInfo.senderID, sysMessage)
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)
    WCM.userJoinedGroup(requestInfo.senderID, groupID)
    WCM.userJoinedGroup(requestInfo.target, groupID)

    FRIEND_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

    # 推送申请结果
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
    # await SCM.sending(requestInfo.target, sysMessage)
    await WCM.sendingSystemMessage(requestInfo.target, sysMessage)

    joinedMessage = GetMessageSchema(
        time=timestamp(),
        type="system",
        group=groupID,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content="我们已经是好友了，一起来聊天吧！",
        )
    )
    # await GCM.sending(groupID, userInfo.uuid, joinedMessage)
    await WCM.sendingSystemMessage(userInfo.uuid, groupID, joinedMessage)

    return {"detail": "ok"}


@userRouter.delete('/{uuid}/verify/request/{time}')
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
    FRIEND_REQUEST.update(
        {"time": time},
        {"$set": {"state": RequestState.REJECTED.value}}
    )

    return {"detail": "ok"}
