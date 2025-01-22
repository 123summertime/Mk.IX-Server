import asyncio
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from depends import PermissionValidate, TargetValidate, CheckPermission, RequestValidate, CheckTarget, \
    CheckRequest, OutputFileValidate, getGroupInfoWithAvatar, getSelfInfo
from schema import InputValidate, FileInput, GroupSchema, Info, GroupA, GroupQA, GroupRegister, Avatar, \
    Reason, GroupName, GroupAnnouncement,  GetMessageSchema, SysMessageSchema, MessagePayload, \
    BroadcastMessageSchema, RequestMsgSchema, FileStorageSchema, NotificationMsgSchema, UserSchema, GroupBan, \
    BroadcastMeta
from public import API, Default, Limits, Database, RequestState, SystemMessageType, NotificationMsgSubtype
from utils import ACCOUNT, GROUP, FS, CrudHelpers, GROUP_REQUEST, timestamp, rateLimit, WCM

groupRouter = APIRouter(prefix=f"/{API.VERSION.value}/group", tags=['Group'])


@groupRouter.post("/register")
@rateLimit(5, 30)
async def makeGroup(groupRegister: GroupRegister,
                    userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    创建群
    '''
    name, Q, A = groupRegister.name, groupRegister.Q, groupRegister.A
    time = timestamp()
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Default.DEFAULT_AVATAR.value,
        lastUpdate=time,
        owner=userInfo.id,
        question={Q: A},
        admin=[],
        user=[userInfo.id],
    ).model_dump(exclude={"id"})

    groupObjID = GROUP.add(newGroup).inserted_id
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )
    Database.CLIENT.value[Database.STORAGE_DB.value][groupID].create_index([('time', 1)], unique=True)

    WCM.userJoinedGroup(userInfo.uuid, groupID, "group")

    # 发送创建群的广播消息
    buildMessage = BroadcastMessageSchema(
        time=time,
        type="system",
        group=groupID,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{name}群已创建",
            meta=BroadcastMeta(
                operation="group_create",
                var={
                    "id": groupID,
                    "name": name,
                }
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, buildMessage))

    return {"groupID": groupID}


@groupRouter.delete('/{group}')
@rateLimit(10, 30)
async def deleteGroup(info: Info = Depends(CheckPermission(PermissionValidate.owner))):
    '''
    解散群 仅群主可用
    '''
    userInfo, groupInfo = info.userInfo, info.groupInfo
    time = timestamp()

    for objID in groupInfo.user:
        ACCOUNT.update(
            {"_id": objID},
            {"$pull": {"groups": groupInfo.id}}
        )
    GROUP.delete(
        {"group": groupInfo.group}
    )

    # 发送解散群的广播消息
    dismissMessage = BroadcastMessageSchema(
        time=time,
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content="该群已被群主解散",
            meta=BroadcastMeta(
                operation="group_disband",
                var={
                    "id": groupInfo.group,
                },
            )
        )
    )
    await WCM.sendingGroupMessage(userInfo.uuid, dismissMessage)

    # 发送解散通知
    for userObjID in groupInfo.user:
        targetInfo = CrudHelpers.userObjectIDtoInfo(userObjID)
        notificationMessage = NotificationMsgSchema(
            time=time,
            subType=NotificationMsgSubtype.NEGATIVE.value,
            isGroupMessage=True,
            target=targetInfo.uuid,
            blank="",
            payload=f'群"{groupInfo.name}"已解散',
            meta=BroadcastMeta(
                operation="group_disband",
                var={
                    "id": groupInfo.group,
                    "type": "group",
                }
            )
        )
        asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))

    WCM.disconnectGroup(groupInfo.group)

    return {"detail": "ok"}


@groupRouter.get('/{group}/members')
@rateLimit(10, 30)
async def getMembersInfo(info: Info = Depends(CheckPermission(PermissionValidate.member))):
    '''
    获取群成员信息 群员权限
    '''
    groupInfo = info.groupInfo
    membersInfo = [CrudHelpers.userObjectIDtoInfo(i).model_dump() for i in groupInfo.user]

    return {"users": membersInfo}


@groupRouter.get('/{group}/announcement')
@rateLimit(10, 30)
async def getAnnouncement(info: Info = Depends(CheckPermission(PermissionValidate.member))):
    '''
    获取群公告
    '''
    groupInfo = info.groupInfo

    return {"announcement": groupInfo.announcement}


@groupRouter.patch('/{group}/announcement')
@rateLimit(10, 30)
async def modifyAnnouncement(ann: GroupAnnouncement,
                             info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    修改群公告
    '''
    ann, groupInfo = ann.announcement, info.groupInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {"announcement": ann}},
    )

    return {"detail": "ok"}


@groupRouter.get('/{group}/members/admin')
@rateLimit(10, 30)
async def getAdminInfo(info: Info = Depends(CheckPermission(PermissionValidate.notLimit))):
    '''
    获取群主+管理员信息 需要登录
    '''
    groupInfo = info.groupInfo
    res = {
        "owner": CrudHelpers.userObjectIDtoInfo(groupInfo.owner).model_dump(),
        "admin": [CrudHelpers.userObjectIDtoInfo(i).model_dump() for i in groupInfo.admin]
    }

    return res


@groupRouter.delete("/{group}/members/me")
@rateLimit(10, 30)
async def deleteSelf(info: Info = Depends(CheckPermission(PermissionValidate.member,
                                                          PermissionValidate.notOwner))):
    '''
    退出群 群员可用 群主除外
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"admin": userInfo.id, "user": userInfo.id}}
    )
    ACCOUNT.update(
        {"_id": userInfo.id},
        {"$pull": {"groups": groupInfo.id}}
    )

    # 广播退群消息
    removeMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{userInfo.username}已退出该群",
            meta=BroadcastMeta(
                operation="group_leave",
                var={
                    "id": userInfo.uuid,
                    "name": userInfo.username,
                    "operator": userInfo.uuid,
                }
            )
        )
    )
    await WCM.sendingGroupMessage(userInfo.uuid, removeMessage)
    WCM.disconnectUserFromGroup(userInfo.uuid, groupInfo.group)

    return {"detail": "ok"}


@groupRouter.get("/{group}/members/{uuid}/ban")
@rateLimit(30, 30)
async def getUserBanState(info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                          info2: Info = Depends(CheckTarget(TargetValidate.member))):
    '''
    获取群内用户禁言状态
    '''
    info |= info2
    groupInfo, targetInfo = info.groupInfo, info.targetInfo
    if targetInfo.uuid not in groupInfo.ban or groupInfo.ban[targetInfo.uuid] < timestamp():
        return {"ban": False, "time": ""}
    return {"ban": True, "time": groupInfo.ban[targetInfo.uuid]}


@groupRouter.post("/{group}/members/{uuid}/ban")
@rateLimit(30, 30)
async def banUser(t: GroupBan,
                  info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                  info2: Info = Depends(CheckTarget(TargetValidate.member,
                                                    TargetValidate.notSelf,
                                                    TargetValidate.notOwner))):
    '''
    设置群禁言
    '''
    info |= info2
    userInfo, groupInfo, targetInfo = info.userInfo, info.groupInfo, info.targetInfo

    endTime = str(int(timestamp()) + (t.duration * 60 * 1000))
    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {f"ban.{targetInfo.uuid}": endTime}}
    )
    WCM.updateGroupBan(groupInfo.group, targetInfo.uuid, endTime)

    banMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{targetInfo.username}已被禁言{str(t.duration)}分钟" if t.duration else f"{targetInfo.username}已被解除禁言",
            meta=BroadcastMeta(
                operation="group_ban" if t.duration else "group_lift_ban",
                var={
                    "id": targetInfo.uuid,
                    "name": targetInfo.username,
                    "duration": t.duration,
                    "operator": userInfo.uuid,
                }
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, banMessage))

    return {"detail": "ok"}


@groupRouter.delete("/{group}/members/{uuid}")
@rateLimit(30, 30)
async def deleteUser(info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                     info2: Info = Depends(CheckTarget(TargetValidate.member,
                                                       TargetValidate.notSelf,
                                                       TargetValidate.notOwner,
                                                       TargetValidate.notAdmin))):
    '''
    踢出群，群主/管理员可用
    '''
    info |= info2
    userInfo, targetInfo, groupInfo = info.userInfo, info.targetInfo, info.groupInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"user": targetInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$pull": {"groups": groupInfo.id}}
    )

    # 广播消息
    removeMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{targetInfo.username}已被移出群聊",
            meta=BroadcastMeta(
                operation="group_kick",
                var={
                    "id": targetInfo.uuid,
                    "name": targetInfo.username,
                    "operator": userInfo.uuid,
                }
            )
        )
    )
    await WCM.sendingGroupMessage(userInfo.uuid, removeMessage)

    # 向被移除的人发送通知
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.NEGATIVE.value,
        isGroupMessage=True,
        target=targetInfo.uuid,
        blank=groupInfo.group,
        payload='你已被移出群{}',
        meta=BroadcastMeta(
            operation="group_kick",
            var={
                "id": groupInfo.group,
                "type": "group",
                "operator": userInfo.uuid,
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))
    WCM.disconnectUserFromGroup(targetInfo.uuid, groupInfo.group)

    return {"detail": "ok"}


@groupRouter.post("/{group}/members/admin/{uuid}")
@rateLimit(30, 30)
async def addAdmin(info: Info = Depends(CheckPermission(PermissionValidate.owner)),
                   info2: Info = Depends(CheckTarget(TargetValidate.notOwner,
                                                     TargetValidate.notAdmin,
                                                     TargetValidate.member))):
    '''
    增加管理员，仅群主可用
    '''
    info |= info2
    groupInfo, targetInfo = info.groupInfo, info.targetInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$push": {"admin": targetInfo.id}}
    )

    # 发送向目标用户发送通知消息
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.POSITIVE.value,
        isGroupMessage=True,
        target=targetInfo.uuid,
        blank=groupInfo.group,
        payload='你已成为群{}的管理员',
        meta=BroadcastMeta(
            operation="group_admin_set",
            var={
                "id": groupInfo.group,
                "type": "group",
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))

    return {"detail": "ok"}


@groupRouter.delete("/{group}/members/admin/{uuid}")
@rateLimit(30, 30)
async def deleteAdmin(info: Info = Depends(CheckPermission(PermissionValidate.owner)),
                      info2: Info = Depends(CheckTarget(TargetValidate.admin))):
    '''
    删除管理员，仅群主可用
    '''
    info |= info2
    groupInfo, targetInfo = info.groupInfo, info.targetInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"admin": targetInfo.id}}
    )

    # 发送向目标用户发送通知消息
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.NEGATIVE.value,
        isGroupMessage=True,
        target=targetInfo.uuid,
        blank=groupInfo.group,
        payload='你已被移出群{}的管理员',
        meta=BroadcastMeta(
            operation="group_admin_unset",
            var={
                "id": groupInfo.group,
                "type": "group",
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))

    return {"detail": "ok"}


@groupRouter.get('/{group}/info')
async def getInfo(groupInfo: GroupSchema = Depends(getGroupInfoWithAvatar)):
    '''
    获取群信息
    '''
    info = {
        "name": groupInfo.name,
        "avatar": groupInfo.avatar,
        "lastUpdate": groupInfo.lastUpdate
    }

    return info


@groupRouter.patch('/{group}/info/name')
@rateLimit(10, 30)
async def modifyGroupName(newName: GroupName,
                          info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    修改群名 管理员权限
    '''
    userInfo, groupInfo = info.userInfo, info.groupInfo
    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {"name": newName.name, "lastUpdate": timestamp()}}
    )

    # 发送修改群名的广播消息
    message = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f'{userInfo.username}修改群名为{newName.name}',
            meta=BroadcastMeta(
                operation="group_rename",
                var={
                    "id": userInfo.uuid,
                    "name": userInfo.username,
                    "new_name": newName.name,
                }
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, message))

    return {"detail": "ok"}


@groupRouter.patch('/{group}/info/avatar')
@rateLimit(5, 30)
async def modifyGroupAvatar(newAvatar: Avatar,
                            info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    修改群头像 管理员权限
    '''
    groupInfo = info.groupInfo
    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {"avatar": newAvatar.avatar, "lastUpdate": timestamp()}}
    )

    return {"detail": "ok"}


@groupRouter.patch('/{group}/verify/question')
@rateLimit(10, 30)
async def modifyGroupQA(groupQA: GroupQA,
                        info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    groupInfo = info.groupInfo
    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {"question": {groupQA.Q: groupQA.A}}},
    )

    return {"detail": "ok"}


@groupRouter.get("/{group}/verify/question")
@rateLimit(10, 30)
async def joinQuestion(info: Info = Depends(CheckPermission(PermissionValidate.notLimit))):
    '''
    获取群人数及入群问题
    '''
    userInfo, groupInfo = info.userInfo, info.groupInfo
    if not groupInfo.question or not list(groupInfo.question.keys())[0]:
        raise HTTPException(status_code=403, detail="该群不允许被搜索")

    info = {
        "member": len(groupInfo.user),
        "question": list(groupInfo.question.keys())[0],
        "lastUpdate": groupInfo.lastUpdate,
    }
    return info


@groupRouter.post("/{group}/verify/answer")
@rateLimit(10, 120)
async def join(answer: GroupA,
               info: Info = Depends(CheckPermission(PermissionValidate.notMember))):
    '''
    通过回答问题加入群聊 非群员权限
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if answer.A != list(groupInfo.question.values())[0]:
        raise HTTPException(status_code=400, detail="答案错误")

    # 如果存在发出的入群申请，则删除
    GROUP_REQUEST.delete(
        {"group": groupInfo.group, "senderID": userInfo.uuid, "state": RequestState.PENDING.value},
    )
    GROUP.update(
        {"group": groupInfo.group},
        {"$push": {"user": userInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupInfo.id}}
    )

    WCM.userJoinedGroup(userInfo.uuid, groupInfo.group, "group")

    # 发送用户加入群聊的系统消息
    joinedMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{userInfo.username}加入该群",
            meta=BroadcastMeta(
                operation="group_joined",
                var={
                    "id": userInfo.uuid,
                    "name": userInfo.username,
                    "operator": userInfo.uuid,
                    "way": "qa",
                }
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, joinedMessage))

    # 向用户推送入群成功的系统信息
    sysMessage = SysMessageSchema(
        time=timestamp(),
        type=SystemMessageType.JOINED.value,
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        payload="",
    )
    asyncio.create_task(WCM.sendingSystemMessage(userInfo.uuid, sysMessage))

    return {"detail": "ok"}


@groupRouter.post('/{group}/verify/request')
@rateLimit(10, 30)
async def joinRequest(reason: Reason,
                      info: Info = Depends(CheckPermission(PermissionValidate.notMember)),
                      info2: Info = Depends(
                          lambda userInfo=Depends(getSelfInfo), group=Path(...): CheckRequest(
                              userInfo=userInfo,
                              isGroupRequest=True,
                              group=group,
                              checkers=[RequestValidate.notExist],
                          )()
                      )):
    '''
    入群申请 非群员权限
    '''
    info |= info2
    time = timestamp()
    groupInfo, userInfo = info.groupInfo, info.userInfo

    requestMessage = RequestMsgSchema(
        time=time,
        type=SystemMessageType.JOIN.value,
        target=groupInfo.group,
        senderID=userInfo.uuid,
        payload=reason.reason,
    ).model_dump()
    GROUP_REQUEST.add(requestMessage)

    # 向该群所有管理推送该申请
    sysMessage = SysMessageSchema(
        time=time,
        type=SystemMessageType.JOIN.value,
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        state=RequestState.PENDING.value,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.reason,
    )
    for objID in [groupInfo.owner] + groupInfo.admin:
        info = CrudHelpers.userObjectIDtoInfo(objID)
        asyncio.create_task(WCM.sendingSystemMessage(info.uuid, sysMessage))

    return {"detail": "ok"}


@groupRouter.get('/{group}/verify/request')
async def queryJoinRequest(group: str = Path(...),
                           device: str = Query(...),
                           info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    获取该群的验证消息 管理员权限
    结果也会通过websocket(WCM)发送
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    messages = GROUP_REQUEST.queryMany(  # 获取在有效时间内的请求 单位:ms
        {"target": group, "time": {"$gt": str(int(timestamp()) - Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000)}},
        {"_id": 0}
    )

    res = []
    for msg in messages:
        senderInfo = ACCOUNT.query(
            {"uuid": msg.senderID},
            {"lastUpdate": 1},
        )
        sysMessage = SysMessageSchema(
            time=msg.time,
            type=msg.type,
            target=groupInfo.group,
            targetKey=groupInfo.lastUpdate,
            state=msg.state,
            senderID=msg.senderID,
            senderKey=senderInfo.lastUpdate,
            payload=msg.payload
        )
        res.append(sysMessage.model_dump())
        asyncio.create_task(WCM.sendingSystemMessage(userInfo.uuid, sysMessage, device=device))

    return res


@groupRouter.post('/{group}/verify/request/{time}')
@rateLimit(30, 30)
async def requestAccept(time: str = Path(...),
                        info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                        info2: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), time=Path(...), group=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=True,
                                group=group,
                                time=time,
                                checkers=[RequestValidate.exist],
                            )()
                        )):
    '''
    通过群验证消息，管理员权限
    '''
    info |= info2
    groupInfo, userInfo, targetInfo, requestInfo = info.groupInfo, info.userInfo, info.targetInfo, info.requestInfo
    currentState = (RequestState.ACCEPTED_BY_OWNER.value
                    if userInfo.id == groupInfo.owner
                    else RequestState.ACCEPTED_BY_ADMIN.value)

    GROUP.update(
        {"group": groupInfo.group},
        {"$push": {"user": targetInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$push": {"groups": groupInfo.id}}
    )
    GROUP_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

    WCM.userJoinedGroup(targetInfo.uuid, groupInfo.group, "group")

    # 向用户发送通知消息
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.POSITIVE.value,
        isGroupMessage=True,
        target=targetInfo.uuid,
        blank=groupInfo.group,
        payload='你加入群{}的申请已通过',
        meta=BroadcastMeta(
            operation="group_join_accepted",
            var={
                "id": groupInfo.group,
                "type": "group",
                "operator": userInfo.uuid,
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))
    sysMessage = SysMessageSchema(
        time=timestamp(),
        type=SystemMessageType.JOINED.value,
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        state=currentState,
        payload=""
    )
    asyncio.create_task(WCM.sendingSystemMessage(targetInfo.uuid, sysMessage))

    # 向所有管理推送审核结果
    sysMessage = SysMessageSchema(
        time=requestInfo.time,
        type=requestInfo.type,
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        state=currentState,
        senderID=targetInfo.uuid,
        senderKey=targetInfo.lastUpdate,
        payload=requestInfo.payload
    )
    for objID in [groupInfo.owner] + groupInfo.admin:
        info = CrudHelpers.userObjectIDtoInfo(objID)
        asyncio.create_task(WCM.sendingSystemMessage(info.uuid, sysMessage))

    # 向群中广播加入消息
    joinedMessage = BroadcastMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{targetInfo.username}加入该群",
            meta=BroadcastMeta(
                operation="group_joined",
                var={
                    "id": targetInfo.uuid,
                    "name": targetInfo.username,
                    "operator": userInfo.uuid,
                    "way": "request",
                },
            )
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, joinedMessage))

    return {"detail": "ok"}


@groupRouter.delete('/{group}/verify/request/{time}')
@rateLimit(30, 30)
async def requestReject(time: str = Path(...),
                        info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                        info2: Info = Depends(
                            lambda userInfo=Depends(getSelfInfo), time=Path(...), group=Path(...): CheckRequest(
                                userInfo=userInfo,
                                isGroupRequest=True,
                                group=group,
                                time=time,
                                checkers=[RequestValidate.exist],
                            )()
                        )):
    info |= info2
    groupInfo, userInfo, targetInfo, requestInfo = info.groupInfo, info.userInfo, info.targetInfo, info.requestInfo
    currentState = (RequestState.REJECTED_BY_OWNER.value
                    if userInfo.id == groupInfo.owner
                    else RequestState.REJECTED_BY_ADMIN.value)

    GROUP_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

    # 向用户发送通知消息
    notificationMessage = NotificationMsgSchema(
        time=timestamp(),
        subType=NotificationMsgSubtype.NEGATIVE.value,
        isGroupMessage=True,
        target=targetInfo.uuid,
        blank=groupInfo.group,
        payload='你加入群{}的申请已被拒绝',
        meta=BroadcastMeta(
            operation="group_join_rejected",
            var={
                "id": groupInfo.group,
                "type": "group",
                "operator": userInfo.uuid,
            }
        )
    )
    asyncio.create_task(WCM.sendingNotificationMessage(targetInfo.uuid, groupInfo.name, notificationMessage))

    # 向所有管理推送审核结果
    sysMessage = SysMessageSchema(
        time=requestInfo.time,
        type=requestInfo.type,
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        state=currentState,
        senderID=targetInfo.uuid,
        senderKey=targetInfo.lastUpdate,
        payload=requestInfo.payload
    )
    for objID in [groupInfo.owner] + groupInfo.admin:
        info = CrudHelpers.userObjectIDtoInfo(objID)
        asyncio.create_task(WCM.sendingSystemMessage(info.uuid, sysMessage))

    return {"detail": "ok"}


@groupRouter.post('/{group}/upload')
@rateLimit(10, 30)
async def groupFileUpload(info: Info = Depends(CheckPermission(PermissionValidate.member)),
                          fileInput: FileInput = Depends(InputValidate.validateInputFile)):
    '''
    群上传文件
    '''
    userInfo, groupInfo = info.userInfo, info.groupInfo
    ok, _ = WCM.getGroupBan(groupInfo.group, userInfo.uuid)
    if not ok:
        raise HTTPException(status_code=403, detail="您已被禁言")

    time = timestamp()
    fileName, fileType, content = fileInput.fileName, fileInput.fileType, fileInput.content
    groupInfo, userInfo = info.groupInfo, info.userInfo
    hashcode = FS.add(content, fileName, fileType, groupInfo.group)

    message = GetMessageSchema(
        time=time,
        type=fileType,
        group=groupInfo.group,
        groupType="group",
        senderID=userInfo.uuid,
        payload=MessagePayload(
            name=fileName,
            size=len(content),
            content=hashcode,
        )
    )
    asyncio.create_task(WCM.sendingGroupMessage(userInfo.uuid, message))

    API.LOGGER.value.info(f"{userInfo.uuid} 在 {groupInfo.group}(group) 发送了 {fileType} 类型的消息({time})")
    return {"time": time}


@groupRouter.get('/{group}/download/{hashcode}')
@rateLimit(10, 30)
async def downloadFile(info: Info = Depends(CheckPermission(PermissionValidate.member)),
                       file: FileStorageSchema = Depends(OutputFileValidate.existsGroup)):
    READ_SIZE = 1024 * 1024  # 1MB

    def iter():
        while chunk := file.file.read(READ_SIZE):
            yield chunk

    res = StreamingResponse(iter(), media_type=file.type)
    res.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(file.name)}"
    res.headers["Content-Length"] = str(file.file.length)
    return res
