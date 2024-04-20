from typing import List
from uuid import uuid4
import base64

from const import API, Database, Collection, Miscellaneous
from stateCode import RequestState
from depend.getInfo import getSelfInfo, getGroupInfo, getGroupInfoWithAvatar, getUserInfo
from depend.permission import NonePermission, UserPermission, AdminPermission, OwnerPermission
from utils.dbCRUD import DB_CRUD
from utils.helper import timestamp, convertObjectIDtoInfo
from utils.wsConnectionMgr import GCM, SCM
from schema.user import UserSchema
from schema.group import GroupSchema
from schema.payload import GroupQA, GroupRegister, Info, Note
from schema.storage import RequestMsgSchema
from schema.message import SysMessageSchema

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer


groupRouter = APIRouter(prefix=f"/{API.version.value}/group", tags=['Group'])


@groupRouter.post("/")
def makeGroup(registerInfo: GroupRegister,
              userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    创建群
    '''
    name, Q, A = registerInfo.name, registerInfo.Q, registerInfo.A
    nameMinLength, nameMaxLength = Miscellaneous.GROUP_NAME_LENGTH_RANGE.value
    QAMinLength, QAMaxLength = Miscellaneous.GROUP_QA_LENGTH_RANGE.value

    if not nameMinLength <= len(name) <= nameMaxLength:
        raise HTTPException(status_code=400, detail=f"群名长度必须在[{nameMinLength}, {nameMaxLength}]以内")
    if (not QAMinLength <= len(Q) <= QAMaxLength) or (not QAMinLength <= len(A) <= QAMaxLength):
        raise HTTPException(status_code=400, detail=f"问题和答案长度必须在[{QAMinLength}, {QAMaxLength}]以内")

    groupID = str(uuid4().int)[::4]

    newGroup = dict(GroupSchema(
        group=groupID,
        name=name,
        avatar=Miscellaneous.DEFAULT_AVATAR.value,
        lastUpdate=timestamp(),
        owner=userInfo.id,
        question={Q: A},
        admin=[],
        user=[userInfo.id],
    ))

    del newGroup["id"]

    groupObjID = Collection.GROUP.value.add(dict(newGroup)).inserted_id
    Collection.ACCOUNT.value.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )

    return {"groupID": groupID}


# getGroupInfo
@groupRouter.get('/{group}')
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


@groupRouter.delete('/{group}')
def deleteGroup(info: Info = Depends(OwnerPermission)):
    '''
    解散群 仅群主可用
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    for objID in groupInfo.user:
        Collection.ACCOUNT.value.update(
            {"_id": objID},
            {"$pull": {"groups": groupInfo.id}}
        )
    Collection.GROUP.value.delete(
        {"group": groupInfo.group}
    )
    GCM.removeGroup(groupInfo.group)

    return {"state": 1}


@groupRouter.delete("/{group}/me")
def deleteSelf(info: Info = Depends(UserPermission)):
    '''
    退出群 群员可用 群主除外
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if userInfo.id == groupInfo.owner:
        raise HTTPException(status_code=400, detail="群主不允许退出群，请使用解散群")

    if userInfo.id in groupInfo.admin:
        Collection.GROUP.value.update(
            {"group": groupInfo.group},
            {"$pull": {"admin": userInfo.id}}
        )
    Collection.GROUP.value.update(
        {"group": groupInfo.group},
        {"$pull": {"user": userInfo.id}}
    )
    Collection.ACCOUNT.value.update(
        {"_id": userInfo.id},
        {"$pull": {"groups": groupInfo.id}}
    )
    GCM.removeSomeoneInGroup(groupInfo.group, userInfo.uuid)

    return {"state": 1}


@groupRouter.delete("/{group}/{target}")
def deleteUser(info: Info = Depends(AdminPermission),
               targetInfo: UserSchema = Depends(getUserInfo)):
    '''
    踢出群，群主/管理员可用
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if userInfo.id == targetInfo.id:
        raise HTTPException(status_code=400, detail="不能移除自己")
    if targetInfo.id not in groupInfo.user:
        raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 不在群 {groupInfo.name} 内")

    Collection.GROUP.value.update(
        {"group": groupInfo.group},
        {"$pull": {"user": targetInfo.id}}
    )
    Collection.ACCOUNT.value.update(
        {"uuid": userInfo.uuid},
        {"$pull": {"groups": groupInfo.id}}
    )
    GCM.removeSomeoneInGroup(groupInfo.group, userInfo.uuid)

    return {"state": 1}


@groupRouter.get('/{group}/admin')
def getAdminInfo(groupInfo: GroupSchema = Depends(getGroupInfo)):
    '''
    获取群主+管理员信息 无需权限
    '''
    info = {
        "owner": dict(convertObjectIDtoInfo(groupInfo.owner)),
        "admin": [dict(convertObjectIDtoInfo(i)) for i in groupInfo.admin]
    }

    return info


@groupRouter.patch("/{group}/admin/{target}")
def admin(operation: bool,
          info: Info = Depends(OwnerPermission),
          targetInfo: UserSchema = Depends(getUserInfo)):
    '''
    增加/减少管理员，仅群主可用
    :param operation: True成为管理员 False撤销管理员
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if groupInfo.owner == targetInfo.id:
        raise HTTPException(status_code=400, detail="群主不可以设为管理员")
    if targetInfo.id not in groupInfo.user:
        raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 不在群 {groupInfo.name} 内")

    if operation:
        if targetInfo.id in groupInfo.admin:
            raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 已经是群 {groupInfo.name} 的管理员")
        Collection.GROUP.value.update(
            {"group": groupInfo.group},
            {"$push": {"admin": targetInfo.id}}
        )
    else:
        if targetInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 不是群 {groupInfo.name} 的管理员")
        Collection.GROUP.value.update(
            {"group": groupInfo.group},
            {"$pull": {"admin": targetInfo.id}}
        )

    return {"state": 1}


@groupRouter.get("/{group}/join")
def joinQuestion(info: Info = Depends(NonePermission)):
    '''
    获取入群问题 无权限
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if groupInfo.id in userInfo.groups:
        raise HTTPException(status_code=400, detail="已经加入了")

    info = {
        "name": groupInfo.name,
        "question": list(groupInfo.question.keys())[0]
    }

    return info


@groupRouter.post("/{group}/join")
def join(answer: GroupQA,
         info: Info = Depends(NonePermission)):
    '''
    通过回答问题加入群聊 无权限
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    if groupInfo.id in userInfo.groups:
        raise HTTPException(status_code=400, detail="已经加入了")
    if answer.A != list(groupInfo.question.values())[0]:
        raise HTTPException(status_code=400, detail="答案错误")

    Collection.GROUP.value.update(
        {"group": groupInfo.group},
        {"$push": {"user": userInfo.id}}
    )
    Collection.ACCOUNT.value.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupInfo.id}}
    )

    return {"state": 1}


@groupRouter.patch('/{group}/name')
def modifyGroupName(newName: Note,
                    info: Info = Depends(AdminPermission)):
    '''
    修改群名 管理员权限
    '''
    groupInfo, _ = info.groupInfo, info.userInfo
    nameMinLength, nameMaxLength = Miscellaneous.GROUP_NAME_LENGTH_RANGE.value

    if not (nameMinLength <= len(newName.note) <= nameMaxLength):
        raise HTTPException(status_code=400, detail=f"群名长度必须在[{nameMinLength}, {nameMaxLength}]以内")

    Collection.GROUP.value.update(
        {"group": groupInfo.group},
        {"$set": {"name": newName.note, "lastUpdate": timestamp()}}
    )

    return {"state": 1}


@groupRouter.patch('/{group}/avatar')
def modifyGroupAvatar(newAvatar: Note,
                      info: Info = Depends(AdminPermission)):
    '''
    修改群头像 管理员权限
    '''
    avatar = newAvatar.note
    groupInfo, _ = info.groupInfo, info.userInfo
    avatarMinSize, avatarMaxSize = Miscellaneous.GROUP_AVATAR_MIN_SIZE.value

    # 初步判定大小 1KB文件编码后约为1400字符
    if len(avatar) > avatarMaxSize * 1400:
        raise HTTPException(status_code=400, detail=f"文件大小必须在[{avatarMinSize}, {avatarMaxSize}]KB以内")

    img = base64.b64decode(avatar.split(',')[1])
    size = len(img) // 1024
    if not (avatarMinSize <= size <= avatarMaxSize):
        raise HTTPException(status_code=400, detail=f"文件大小必须在[{avatarMinSize}, {avatarMaxSize}]KB以内")

    Collection.GROUP.value.update(
        {"group": groupInfo.group},
        {"$set": {"avatar": avatar, "lastUpdate": timestamp()}}
    )

    return {"state": 1}


@groupRouter.get('/{group}/user')
def getMembersInfo(info: Info = Depends(UserPermission)):
    '''
    获取群成员信息 群员权限
    '''
    groupInfo, _ = info.groupInfo, info.userInfo

    membersInfo = [dict(convertObjectIDtoInfo(i)) for i in groupInfo.user]

    return {"users": membersInfo}


@groupRouter.post('/{group}/request')
async def joinRequest(joinText: Note,
                      info: Info = Depends(NonePermission)):
    '''
    入群申请 非群员权限
    '''
    time = timestamp()
    groupInfo, userInfo = info.groupInfo, info.userInfo
    reqCollection = DB_CRUD(Database.ReqDB.value, groupInfo.group, RequestMsgSchema)
    admins = groupInfo.admin + [groupInfo.owner]

    if groupInfo.id in userInfo.groups:
        raise HTTPException(status_code=400, detail="已经加入了该群")

    requestExist = reqCollection.query(
        {"senderID": userInfo.uuid},
        {"time": 1, "state": 1}
    )

    if not requestExist:
        raise HTTPException(status_code=400, detail="申请不存在")

    if requestExist and requestExist.state == 0 and int(timestamp()[:10]) - int(requestExist.time[:10]) \
            < int(Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60):
        raise HTTPException(status_code=400, detail="申请中，等待审核")

    sysMessage = SysMessageSchema(
        time=time,
        type="join",
        group=groupInfo.group,
        groupKey=groupInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=joinText.note,
    )

    requestMessage = RequestMsgSchema(
        time=time,
        type="join",
        group=groupInfo.group,
        groupKey=groupInfo.lastUpdate,
        senderID=userInfo.uuid,
        senderKey=userInfo.lastUpdate,
        payload=joinText.note,
    )

    reqCollection.add(dict(requestMessage))

    for objID in admins:
        info = convertObjectIDtoInfo(objID)
        if info.uuid in SCM:
            await SCM.sending(info.uuid, dict(sysMessage))

    return {"state": 1}


@groupRouter.get('/{group}/request')
async def queryJoinRequest(info: Info = Depends(AdminPermission)):
    '''
    获取群验证消息 管理员权限
    结果通过ws发送
    '''
    groupInfo, userInfo = info.groupInfo, info.userInfo

    reqCollection = DB_CRUD(Database.ReqDB.value, groupInfo.group, RequestMsgSchema)
    messages = reqCollection.queryMany(  # 获取在有效时间内的请求
        {"time": {"$gt": str(int(timestamp()) - Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60 * 1000 * 1000)}},
        {"_id": 0}
    )

    for msg in messages:
        sysMessage = SysMessageSchema(
            time=msg.time,
            type=msg.type,
            group=groupInfo.group,
            groupKey=groupInfo.lastUpdate,
            state=msg.state,
            senderID=msg.senderID,
            senderKey=msg.senderKey,
            payload=msg.payload
        )

        if userInfo.uuid in SCM:
            await SCM.sending(userInfo.uuid, dict(sysMessage))


@groupRouter.post('/{group}/response')
async def requestResponse(verdict: bool,
                          time: Note,
                          info: Info = Depends(AdminPermission)):
    '''
    验证群验证消息，管理员权限
    verdict: True通过 False不通过
    '''
    time = time.note
    groupInfo, userInfo = info.groupInfo, info.userInfo
    admins = groupInfo.admin + [groupInfo.owner]

    if int(time) < int(timestamp()) - Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60 * 1000 * 1000:
        raise HTTPException(status_code=400, detail="请求已过期")

    reqCollection = DB_CRUD(Database.ReqDB.value, groupInfo.group, RequestMsgSchema)
    requestInfo = reqCollection.query(
        {"time": time},
        {"_id": 0}
    )

    if not requestInfo:
        raise HTTPException(status_code=400, detail="该请求不存在")
    if requestInfo.state != RequestState.PENDING.value:
        raise HTTPException(status_code=403, detail="已被群主或其他管理员同意/拒绝")

    if verdict:
        currentState = (RequestState.ACCEPTED_BY_OWNER.value
                        if userInfo.id == groupInfo.owner
                        else RequestState.ACCEPTED_BY_ADMIN.value)

        # Collection.GROUP.value.update(
        #     {"group": groupInfo.group},
        #     {"$push": {"user": userInfo.id}}
        # )
        # Collection.ACCOUNT.value.update(
        #     {"uuid": userInfo.id},
        #     {"$push": {"groups": groupInfo.id}}
        # )

        if requestInfo.senderID in SCM:
            sysMessage = SysMessageSchema(
                time=timestamp(),
                type="joined",
                group=groupInfo.group,
                state=currentState,
                payload=groupInfo.name
            )
            await SCM.sending(requestInfo.senderID, dict(sysMessage))

    else:
        currentState = (RequestState.REJECTED_BY_OWNER.value
                        if userInfo.id == groupInfo.owner
                        else RequestState.REJECTED_BY_ADMIN.value)

    # reqCollection.update(
    #     {"time": time},
    #     {"$set": {"state": currentState}}
    # )

    sysMessage = SysMessageSchema(
        time=requestInfo.time,
        type=requestInfo.type,
        group=groupInfo.group,
        groupKey=requestInfo.groupKey,
        state=currentState,
        senderID=requestInfo.senderID,
        senderKey=requestInfo.senderKey,
        payload=requestInfo.payload
    )

    for objID in admins:
        info = convertObjectIDtoInfo(objID)
        if info.uuid in SCM:
            await SCM.sending(info.uuid, dict(sysMessage))

    return {"state": 1}


@groupRouter.post('/invite')
def inviteRequest(targetGroup: str, user: UserSchema = Depends(getSelfInfo)):
    '''
    入群邀请
    :param targetGroup: 目标群号
    :param user: 用户信息
    '''
    # groupConfig下邀请
    groupInfo = Collection.GROUP.value.query(
        {"group": targetGroup},
        {"_id": 1, "question": 1, "owner": 1, "admin": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")

    time = timestamp()

    if not groupInfo:
        pass

    if user["_id"] != groupInfo.owner and user["_id"] not in groupInfo.admin:
        raise HTTPException(status_code=403, detail="仅群主/管理员可以邀请")


@groupRouter.post('/friendRequest')
def friendRequest(targetUser: str, user: UserSchema = Depends(getSelfInfo)):
    # 个人profile下发起
    pass
