from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from depends.getInfo import getSelfInfo, getUserInfo, checker, getUserInfoWithAvatar
from public.const import API, Auth, Default, Database, Limits
from public.stateCode import RequestState
from schema.group import GroupSchema
from schema.message import SysMessageSchema, MessagePayload, GetMessageSchema
from schema.payload import Register, Note
from schema.storage import RequestMsgSchema
from schema.user import UserSchema
from utils.crud import ACCOUNT, GROUP, DB_CRUD
from utils.helper import hashPassword, timestamp, createAccessToken
from utils.wsConnectionMgr import SCM, GCM

userRouter = APIRouter(prefix=f"/{API.VERSION.value}/user", tags=['User'])


@userRouter.post('/register')
def register(registerInfo: Register):
    '''
    用户注册
    '''
    userName, password = registerInfo.userName, registerInfo.password
    hashedPassword = hashPassword(password)

    userID = str(uuid4().int)[::4]
    userInfo = UserSchema(
        uuid=userID,
        userName=userName,
        password=hashedPassword,
        avatar=Default.DEFAULT_AVATAR.value,
        bio="",
        lastSeen=timestamp(),
        lastUpdate=timestamp(),
        groups=[],
    )

    ACCOUNT.add(dict(userInfo))

    info = {"uuid": userID}

    return info


@userRouter.post('/token')
def token(formData: OAuth2PasswordRequestForm = Depends(), isBot: bool = False):
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
    token = createAccessToken(
        {"uuid": formData.username, "bot": isBot},
        accessTokenExpires
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@userRouter.get('/check')
def check(newToken=Depends(checker)):
    '''
    验证token是否有效
    :return: 按需刷新token
    '''
    return newToken


@userRouter.get('/profile/me')
def profile(userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取自己的信息 需要登录
    不包括avatar和password  avatar通过GET profile/{uuid}获取
    '''
    for index, groupObjID in enumerate(userInfo.groups):
        groupInfo = GROUP.query(
            {"_id": groupObjID},
            {"_id": 0, "group": 1, "lastUpdate": 1}
        )
        userInfo.groups[index] = dict(groupInfo)

    info = dict(userInfo)
    del info["id"]

    return info


@userRouter.get('/profile/{uuid}')
def userInfo(userInfo: UserSchema = Depends(getUserInfoWithAvatar)):
    '''
    获取用户信息
    :param uuid: 用户uuid
    :return: 用户的userName, avatar, lastUpdate
    '''
    info = {
        "userName": userInfo.userName,
        "avatar": userInfo.avatar,
        "lastUpdate": userInfo.lastUpdate,
    }

    return info


@userRouter.get('/profile/current/{uuid}')
def getUserCurrentInfo(userCurrentInfo: UserSchema = Depends(getUserInfo)):
    '''
    获取用户当前信息
    :param uuid: 用户uuid
    :return: 用户的lastSeen, bio
    '''
    if userCurrentInfo.uuid in SCM:
        userCurrentInfo.lastSeen = "Online"

    info = {
        "bio": userCurrentInfo.bio,
        "lastSeen": userCurrentInfo.lastSeen,
    }

    return info


@userRouter.post('/{uuid}/friend')
async def friendRequest(reason: Note,
                        userInfo: UserSchema = Depends(getSelfInfo),
                        targetInfo: UserSchema = Depends(getUserInfo)):
    '''
    发送加好友请求
    '''
    time = timestamp()
    reqCollection = DB_CRUD(Database.REQUEST_DB.value, Database.FRIEND_REQUEST_DB.value, RequestMsgSchema)

    requestExist = reqCollection.query(
        {"senderID": userInfo.uuid},
        {"time": 1, "state": 1}
    )

    if requestExist \
            and requestExist.state == RequestState.PENDING.value \
            and int(timestamp()) - int(requestExist.time) < int(Limits.FRIEND_REQUEST_EXPIRE_MINUTES.value * 60 * 1000):
        raise HTTPException(status_code=400, detail="已经申请过了")

    sysMessage = SysMessageSchema(
        time=time,
        type="friend",
        target=targetInfo.uuid,
        targetKey=targetInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.note,
    )

    requestMessage = RequestMsgSchema(
        time=time,
        type="friend",
        target=targetInfo.uuid,
        targetKey=targetInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.note,
    )

    reqCollection.add(requestMessage.model_dump())

    if targetInfo.uuid in SCM:
        await SCM.sending(targetInfo.uuid, sysMessage.model_dump())

    return {"detail": "ok"}


@userRouter.get('/{uuid}/verify/request')
async def queryFriendRequest(userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取好友申请
    结果通过ws(SCM)发送
    '''

    reqCollection = DB_CRUD(Database.REQUEST_DB.value, Database.FRIEND_REQUEST_DB.value, RequestMsgSchema)
    messages = reqCollection.queryMany(  # 获取在有效时间内的请求 单位:ms
        {"target": userInfo.uuid, "time": {"$gt": str(int(timestamp()) - Limits.GROUP_REQUEST_EXPIRE_MINUTES.value * 60 * 1000)}},
        {"_id": 0}
    )

    for msg in messages:
        sysMessage = SysMessageSchema(
            time=msg.time,
            type=msg.type,
            state=msg.state,
            target=msg.target,
            targetKey=msg.targetKey,
            senderID=msg.senderID,
            senderKey=msg.senderKey,
            payload=msg.payload,
        )

        if userInfo.uuid in SCM:
            await SCM.sending(userInfo.uuid, sysMessage.model_dump())


@userRouter.post('/{uuid}/verify/response')
async def requestResponse(verdict: bool,
                          time: Note,
                          userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    验证好友申请
    '''
    time = time.note
    reqCollection = DB_CRUD(Database.REQUEST_DB.value, Database.FRIEND_REQUEST_DB.value, RequestMsgSchema)
    requestInfo = reqCollection.query(
        {"time": time},
        {"_id": 0}
    )

    if int(time) < int(timestamp()) - Limits.FRIEND_REQUEST_EXPIRE_MINUTES.value * 60 * 1000:
        raise HTTPException(status_code=400, detail="请求已过期")
    if not requestInfo:
        raise HTTPException(status_code=400, detail="该请求不存在")
    if requestInfo.state != RequestState.PENDING.value:
        raise HTTPException(status_code=400, detail="已被验证过")
    if requestInfo.target != userInfo.uuid:
        raise HTTPException(status_code=400, detail="非法请求")

    initiator = getUserInfo(requestInfo.senderID)

    if verdict:
        currentState = RequestState.ACCEPTED.value
        name = f"{initiator.userName}和{userInfo.userName}的群聊"
        groupID = str(uuid4().int)[::4]
        newGroup = GroupSchema(
            group=groupID,
            name=name,
            avatar=Default.DEFAULT_AVATAR.value,
            lastUpdate=timestamp(),
            owner=initiator.id,
            question={},
            admin=[],
            user=[initiator.id, userInfo.id],
        ).model_dump()
        del newGroup["id"]

        groupObjID = GROUP.add(newGroup).inserted_id
        ACCOUNT.update(
            {"uuid": initiator.uuid},
            {"$push": {"groups": groupObjID}}
        )
        ACCOUNT.update(
            {"uuid": userInfo.uuid},
            {"$push": {"groups": groupObjID}}
        )

        sysMessage = SysMessageSchema(
            time=timestamp(),
            type="friended",
            target=groupID,
            state=currentState,
            payload=name
        )
        await SCM.sending(requestInfo.senderID, sysMessage.model_dump())
        await SCM.sending(requestInfo.target, sysMessage.model_dump())
    else:
        currentState = RequestState.REJECTED.value

    reqCollection.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

    if userInfo.uuid in SCM:
        sysMessage = SysMessageSchema(
            time=requestInfo.time,
            type=requestInfo.type,
            target=requestInfo.target,
            targetKey=requestInfo.targetKey,
            state=currentState,
            senderID=requestInfo.senderID,
            senderKey=requestInfo.senderKey,
            payload=requestInfo.payload
        )
        await SCM.sending(requestInfo.target, sysMessage.model_dump())

    if verdict:
        joinedMessage = GetMessageSchema(
            time=timestamp(),
            type="system",
            group=groupID,
            senderID=userInfo.uuid,
            payload=MessagePayload(
                content="我们已经是好友了，一起来聊天吧！",
            )
        )
        await GCM.sending(groupID, userInfo.uuid, joinedMessage)

    return {"detail": "ok"}


