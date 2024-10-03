import io
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse

from depends.getInfo import getGroupInfoWithAvatar, getSelfInfo
from depends.inputValidate import InputValidate
from depends.checkPermission import PermissionValidate, TargetValidate, CheckPermission, RequestValidate, CheckTarget, \
    CheckRequest, outputFileValidate
from public.const import API, Database, Default, Limits
from public.stateCode import RequestState
from schema.file import FileInput
from schema.group import GroupSchema, Info
from schema.input import GroupA, GroupRegister, GroupAvatar, Reason, GroupName
from schema.message import GetMessageSchema, SysMessageSchema, MessagePayload
from schema.storage import RequestMsgSchema, FileStorageSchema
from utils.crud import DB_CRUD, ACCOUNT, GROUP, FS, CrudHelpers, GROUP_REQUEST
from utils.helper import timestamp
from utils.wsConnectionMgr import GCM, SCM

groupRouter = APIRouter(prefix=f"/{API.VERSION.value}/group", tags=['Group'])


@groupRouter.post("/register")
def makeGroup(groupRegister: GroupRegister,
              info: Info = Depends(CheckPermission(PermissionValidate.notLimit))):
    '''
    创建群
    '''
    userInfo = info.userInfo
    name, Q, A = groupRegister.name, groupRegister.Q, groupRegister.A
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Default.DEFAULT_AVATAR.value,
        lastUpdate=timestamp(),
        owner=userInfo.id,
        question={Q: A},
        admin=[],
        user=[userInfo.id],
    ).model_dump()
    del newGroup["id"]

    groupObjID = GROUP.add(newGroup).inserted_id
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )

    return {"groupID": groupID}


@groupRouter.delete('/{group}')
async def deleteGroup(info: Info = Depends(CheckPermission(PermissionValidate.owner))):
    '''
    解散群 仅群主可用
    '''
    groupInfo = info.groupInfo

    for objID in groupInfo.user:
        ACCOUNT.update(
            {"_id": objID},
            {"$pull": {"groups": groupInfo.id}}
        )

    GROUP.delete(
        {"group": groupInfo.group}
    )
    await GCM.removeGroup(groupInfo.group)

    return {"detail": "ok"}


@groupRouter.get('/{group}/members')
def getMembersInfo(info: Info = Depends(CheckPermission(PermissionValidate.member))):
    '''
    获取群成员信息 群员权限
    '''
    groupInfo = info.groupInfo
    membersInfo = [CrudHelpers.userObjectIDtoInfo(i).model_dump() for i in groupInfo.user]

    return {"users": membersInfo}


@groupRouter.delete("/{group}/members/me")
async def deleteSelf(info: Info = Depends(CheckPermission(PermissionValidate.member,
                                                          PermissionValidate.notOwner))):
    '''
    退出群 群员可用 群主除外
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"admin": userInfo.id}}
    )
    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"user": userInfo.id}}
    )
    ACCOUNT.update(
        {"_id": userInfo.id},
        {"$pull": {"groups": groupInfo.id}}
    )

    removeMessage = GetMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{userInfo.userName}已退出该群",
        )
    )
    await GCM.sending(groupInfo.group, userInfo.uuid, removeMessage)
    await GCM.removeUser(groupInfo.group, userInfo.uuid)

    return {"detail": "ok"}


@groupRouter.delete("/{group}/members/{uuid}")
async def deleteUser(info: Info = Depends(CheckPermission(PermissionValidate.admin)),
                     info2: Info = Depends(CheckTarget(TargetValidate.member,
                                                       TargetValidate.notSelf,
                                                       TargetValidate.notOwner,
                                                       TargetValidate.notAdmin))):
    '''
    踢出群，群主/管理员可用
    '''
    info |= info2
    groupInfo, userInfo, targetInfo = info.groupInfo, info.userInfo, info.targetInfo

    GROUP.update(
        {"group": groupInfo.group},
        {"$pull": {"user": targetInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": targetInfo.uuid},
        {"$pull": {"groups": groupInfo.id}}
    )

    removeMessage = GetMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{targetInfo.userName}已被移出群聊",
        )
    )
    await GCM.sending(groupInfo.group, userInfo.uuid, removeMessage)
    await GCM.removeUser(groupInfo.group, targetInfo.uuid)

    return {"detail": "ok"}


@groupRouter.get('/{group}/members/admin')
def getAdminInfo(info: Info = Depends(CheckPermission(PermissionValidate.notLimit))):
    '''
    获取群主+管理员信息 需要登录
    '''
    groupInfo = info.groupInfo
    res = {
        "owner": CrudHelpers.userObjectIDtoInfo(groupInfo.owner).model_dump(),
        "admin": [CrudHelpers.userObjectIDtoInfo(i).model_dump() for i in groupInfo.admin]
    }

    return res


@groupRouter.post("/{group}/members/admin/{uuid}")
def addAdmin(info: Info = Depends(CheckPermission(PermissionValidate.owner)),
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

    return {"detail": "ok"}


@groupRouter.delete("/{group}/members/admin/{uuid}")
def deleteAdmin(info: Info = Depends(CheckPermission(PermissionValidate.owner)),
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

    return {"detail": "ok"}


@groupRouter.get('/{group}/info')
def getInfo(groupInfo: GroupSchema = Depends(getGroupInfoWithAvatar)):
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
def modifyGroupName(newName: GroupName,
                    info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    修改群名 管理员权限
    '''
    groupInfo = info.groupInfo
    GROUP.update(
        {"group": groupInfo.group},
        {"$set": {"name": newName.name, "lastUpdate": timestamp()}}
    )

    return {"detail": "ok"}


@groupRouter.patch('/{group}/info/avatar')
def modifyGroupAvatar(newAvatar: GroupAvatar,
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


@groupRouter.get("/{group}/verify/question")
def joinQuestion(info: Info = Depends(CheckPermission(PermissionValidate.notLimit))):
    '''
    获取群人数及入群问题 非群员权限
    '''
    groupInfo = info.groupInfo
    info = {
        "member": len(groupInfo.user),
        "question": list(groupInfo.question.keys())[0],
        "lastUpdate": groupInfo.lastUpdate,
    }

    return info


@groupRouter.post("/{group}/verify/answer")
async def join(answer: GroupA,
               info: Info = Depends(CheckPermission(PermissionValidate.notMember))):
    '''
    通过回答问题加入群聊 非群员权限
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if answer.A != list(groupInfo.question.values())[0]:
        raise HTTPException(status_code=400, detail="答案错误")

    GROUP.update(
        {"group": groupInfo.group},
        {"$push": {"user": userInfo.id}}
    )
    ACCOUNT.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupInfo.id}}
    )

    joinedMessage = GetMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{userInfo.userName}加入该群",
        )
    )
    await GCM.sending(groupInfo.group, userInfo.uuid, joinedMessage)

    return {"detail": "ok"}


@groupRouter.post('/{group}/verify/request')
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
    admins = groupInfo.admin + [groupInfo.owner]

    requestMessage = RequestMsgSchema(
        time=time,
        type="join",
        target=groupInfo.group,
        senderID=userInfo.uuid,
        payload=reason.reason,
    )
    GROUP_REQUEST.add(requestMessage.model_dump())

    sysMessage = SysMessageSchema(
        time=time,
        type="join",
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=reason.reason,
    )
    for objID in admins:
        info = CrudHelpers.userObjectIDtoInfo(objID)
        await SCM.sending(info.uuid, sysMessage)

    return {"detail": "ok"}


@groupRouter.get('/{group}/verify/request')
async def queryJoinRequest(group: str = Path(...),
                           info: Info = Depends(CheckPermission(PermissionValidate.admin))):
    '''
    获取该群的验证消息 管理员权限
    结果通过ws(SCM)发送
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    messages = GROUP_REQUEST.queryMany(  # 获取在有效时间内的请求 单位:ms
        {"target": group, "time": {"$gt": str(int(timestamp()) - Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000)}},
        {"_id": 0}
    )

    for msg in messages:
        sysMessage = SysMessageSchema(
            time=msg.time,
            type=msg.type,
            target=groupInfo.group,
            targetKey=groupInfo.lastUpdate,
            state=msg.state,
            senderID=msg.senderID,
            senderKey=msg.senderKey,
            payload=msg.payload
        )

        await SCM.sending(userInfo.uuid, sysMessage)


@groupRouter.post('/{group}/verify/request/{time}')
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
    admins = groupInfo.admin + [groupInfo.owner]

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

    # 如果申请发起的用户在线，推送加群成功的消息
    sysMessage = SysMessageSchema(
        time=timestamp(),
        type="joined",
        target=groupInfo.group,
        targetKey=groupInfo.lastUpdate,
        state=currentState,
        payload=groupInfo.name
    )
    await SCM.sending(requestInfo.senderID, sysMessage)

    GROUP_REQUEST.update(
        {"time": time},
        {"$set": {"state": currentState}}
    )

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
    for objID in admins:
        info = CrudHelpers.userObjectIDtoInfo(objID)
        await SCM.sending(info.uuid, sysMessage)

    # 向群中广播加入消息

    joinedMessage = GetMessageSchema(
        time=timestamp(),
        type="system",
        group=groupInfo.group,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            content=f"{targetInfo.userName}加入该群",
        )
    )
    await GCM.sending(groupInfo.group, userInfo.uuid, joinedMessage)

    return {"detail": "ok"}


@groupRouter.delete('/{group}/verify/request/{time}')
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

    return {"detail": "ok"}


@groupRouter.post('/{group}/upload')
async def groupFileUpload(info: Info = Depends(CheckPermission(PermissionValidate.member)),
                          fileInput: FileInput = Depends(InputValidate.validateInputFile)):
    '''
    上传文件
    '''
    fileName, fileType, content = fileInput.fileName, fileInput.fileType, fileInput.content
    groupInfo, userInfo = info.groupInfo, info.userInfo
    hashcode = FS.add(content, fileName, fileType, groupInfo.group)

    message = GetMessageSchema(
        time=timestamp(),
        type=fileType,
        group=groupInfo.group,
        senderID=userInfo.uuid,
        payload=MessagePayload(
            name=fileName,
            size=len(content),
            content=hashcode,
        )
    )
    await GCM.sending(groupInfo.group, userInfo.uuid, message)

    return {"detail": "ok"}


@groupRouter.get('/{group}/download/{hashcode}')
def downloadFile(info: Info = Depends(CheckPermission(PermissionValidate.member)),
                 file: FileStorageSchema = Depends(outputFileValidate.exists)):
    res = StreamingResponse(io.BytesIO(file.file), media_type=file.type)
    res.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(file.name)}"
    res.headers["Content-Length"] = str(len(file.file))
    return res
