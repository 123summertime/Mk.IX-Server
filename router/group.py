from typing import List
from uuid import uuid4
import base64

from const import API, Database, Collection, RequestState, Miscellaneous
from depend.depends import getSelfInfo, getGroupInfo, getUserInfo
from utils.dbCRUD import DB_CRUD
from utils.helper import timestamp, objID2info
from utils.wsConnectionMgr import GCM, SCM
from schema.user import UserSchema
from schema.group import GroupSchema
from schema.payload import Avatar, GroupQA, GroupRegister, GroupID
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
    :param registerInfo: 群名，入群问题及答案
    :param userInfo: 用户信息
    :return: 创建的群的uuid
    '''
    name, Q, A = registerInfo.name, registerInfo.Q, registerInfo.A
    nameMinLength, nameMaxLength = Miscellaneous.GROUP_NAME_LENGTH_RANGE.value
    QAMinLength, QAMaxLength = Miscellaneous.GROUP_QA_LENGTH_RANGE.value

    if not nameMinLength <= len(name) <= nameMaxLength:
        raise HTTPException(status_code=400, detail=f"群名长度必须在[{nameMinLength}, {nameMaxLength}]以内")
    if (not QAMinLength <= len(Q) <= QAMaxLength) or (not QAMinLength <= len(A) <= QAMaxLength):
        raise HTTPException(status_code=400, detail=f"问题和答案长度必须在[{QAMinLength}, {QAMaxLength}]以内")

    groupID = str(uuid4().int)[::4]

    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Miscellaneous.DEFAULT_AVATAR.value,
        lastUpdate=timestamp(),
        owner=userInfo.id,
        question={Q: A},
        admin=[],
        user=[userInfo.id],
    ).dict()
    del newGroup["id"]

    groupObjID = Collection.COLL_GRP.value.add(dict(newGroup)).inserted_id
    Collection.COLL_ACC.value.update(
        {"uuid": userInfo.uuid},
        {"$push": {"groups": groupObjID}}
    )

    return {
        "state": 1,
        "groupID": groupID
    }


@groupRouter.delete('/{group}')
def deleteGroup(groupInfo: GroupSchema = Depends(getGroupInfo),
                userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    退出/解散群
    :param groupInfo: 群信息
    :param userInfo: 用户信息
    '''
    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")

    # 为群主时解散 其余成员为退出
    if groupInfo.owner == userInfo.id:
        for objID in groupInfo.user:
            Collection.COLL_ACC.value.update(
                {"_id": objID},
                {"$pull": {"groups": groupInfo.id}}
            )
        Collection.COLL_GRP.value.delete(
            {"group": groupInfo.group}
        )
        GCM.removeGroup(groupInfo.group)
    else:
        if userInfo.id in groupInfo.admin:
            Collection.COLL_GRP.value.update(
                {"group": groupInfo.group},
                {"$pull": {"admin": userInfo.id}}
            )
        Collection.COLL_GRP.value.update(
            {"group": groupInfo.group},
            {"$pull": {"user": userInfo.id}}
        )
        Collection.COLL_ACC.value.update(
            {"_id": userInfo.id},
            {"$pull": {"groups": groupInfo.id}}
        )
        GCM.removeSomeoneInGroup(groupInfo.group, userInfo.uuid)

    return {"state": 1}


@groupRouter.delete("/{group}/{target}")
def deleteUser(groupInfo: GroupSchema = Depends(getGroupInfo),
               targetInfo: UserSchema = Depends(getUserInfo),
               userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    踢出群，群主/管理员可用
    :param groupInfo: 群信息
    :param targetInfo: 被执行对象的信息
    :param userInfo: 用户信息
    '''
    if not targetInfo or targetInfo.id not in groupInfo.user:
        raise HTTPException(status_code=400, detail="目标用户不存在")
    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")
    if userInfo.id != groupInfo.owner and userInfo.id not in groupInfo.admin:
        raise HTTPException(status_code=403, detail="没有权限")
    if userInfo.id == targetInfo.id:
        raise HTTPException(status_code=400, detail="不能移除自己")
    if targetInfo.id == groupInfo.owner or (targetInfo.id in groupInfo.admin and userInfo.id != groupInfo.owner):
        raise HTTPException(status_code=403, detail="没有权限")

    Collection.COLL_GRP.value.update(
        {"group": groupInfo.group},
        {"$pull": {"user": targetInfo.id}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": groupInfo.group},
        {"$pull": {"groups": groupInfo.id}}
    )
    GCM.removeSomeoneInGroup(groupInfo.group, userInfo.uuid)

    return {"state": 1}


@groupRouter.patch("/{group}/admin/{target}")
def admin(operation: bool,
          groupInfo: GroupSchema = Depends(getGroupInfo),
          targetInfo: UserSchema = Depends(getUserInfo),
          userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    增加/减少管理员，仅群主可用
    :param operation: True成为管理员 False取消管理员
    :param targetInfo: 被执行对象
    :param groupInfo: 群号
    :param user: 用户信息
    '''

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")
    if groupInfo.owner != user.id:
        raise HTTPException(status_code=403, detail="没有权限")
    if groupInfo.owner == targetInfo.id:
        raise HTTPException(status_code=400, detail="非法操作")
    if targetInfo.id not in groupInfo.user:
        raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 不在群 {groupInfo.name} 内")

    if operation:
        if targetInfo.id in groupInfo.admin:
            raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 已经是群 {groupInfo.name} 的管理员")
        Collection.COLL_GRP.value.update(
            {"group": groupInfo.group},
            {"$push": {"admin": targetInfo.id}}
        )
    else:
        if targetInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=400, detail=f"{targetInfo.userName} 不是群 {groupInfo.name} 的管理员")
        Collection.COLL_GRP.value.update(
            {"group": groupInfo.group},
            {"$pull": {"admin": targetInfo.id}}
        )

    return {"state": 1}


@groupRouter.get("/{group}/question")
def joinQuestion(groupInfo: GroupSchema = Depends(getGroupInfo),
                 userInfo: UserSchema = Depends(getSelfInfo)):
    '''
    获取入群问题
    :param groupInfo: 群信息
    :param userInfo: 用户信息
    :return: 入群问题
    '''

    if not groupInfo:
        raise HTTPException(status_code=400, detail="Invalid group")
    if groupInfo["_id"] in userInfo["groups"]:
        raise HTTPException(status_code=400, detail="Already Joined")

    return {
        "name": groupInfo["name"],
        "question": list(groupInfo["question"].keys())[0],
    }


@groupRouter.post("/join")
def join(group: str, answer: GroupQA, user: UserSchema = Depends(getSelfInfo)):
    '''
    加入群聊
    :param group: 群号
    :param answer: 入群问题答案
    :param user: 用户信息
    '''
    answer = answer.A

    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "question": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")
    if groupInfo["_id"] in user["groups"]:
        raise HTTPException(status_code=400, detail="已经加入")
    if answer != list(groupInfo["question"].values())[0]:
        raise HTTPException(status_code=400, detail="答案错误")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$push": {"user": user["_id"]}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$push": {"groups": groupInfo["_id"]}}
    )

    return {"state": 1}


@groupRouter.get('/getGroupInfo')
def getInfo(group: str):
    '''
    获取群信息
    :param group: 群号
    :return: 群信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "name": 1, "lastUpdate": 1, "avatar": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")

    return groupInfo


@groupRouter.get('/getAdminInfo')
def getAdminInfo(group: str):
    '''
    获取群主/管理员信息
    :param group: 群号
    :return: 群群主/管理员uuid
    '''
    adminInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "owner": 1, "admin": 1}
    )

    return {
        "owner": objID2info(adminInfo["owner"]),
        "admin": [objID2info(i) for i in adminInfo["admin"]]
    }


@groupRouter.post('/modifyGroupName')
def modifyGroupName(group: str, newName: str, user: UserSchema = Depends(getSelfInfo)):
    '''
    修改群名
    :param group: 群号
    :param newName: 新群名
    :param user: 用户信息
    '''
    nameMinLength, nameMaxLength = Miscellaneous.GROUP_NAME_LENGTH_RANGE.value

    if not (nameMinLength <= len(newName) <= nameMaxLength):
        raise HTTPException(status_code=400, detail=f"Length must between [{nameMinLength}, {nameMaxLength}]")

    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="No permission")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$set": {"name": newName, "lastUpdate": timestamp()}}
    )

    return {"state": 1}


@groupRouter.post('/modifyGroupAvatar')
def modifyGroupAvatar(group: str, newAvatar: Avatar, user: UserSchema = Depends(getSelfInfo)):
    '''
    修改群头像
    :param group: 群号
    :param newAvatar: 新头像
    :param user: 用户信息
    '''
    avatar = newAvatar.avatar

    avatarMinSize, avatarMaxSize = Miscellaneous.GROUP_AVATAR_MIN_SIZE.value

    # 初步判定文件大小 1KB文件编码后约为1400字符
    if len(avatar) > avatarMaxSize * 1400:
        raise HTTPException(status_code=400, detail=f"Size must between [{avatarMinSize}, {avatarMaxSize}]KB")

    img = base64.b64decode(avatar.split(',')[1])
    size = len(img) // 1024
    if not (avatarMinSize <= size <= avatarMaxSize):
        raise HTTPException(status_code=400, detail=f"Size must between [{avatarMinSize}, {avatarMaxSize}]KB")

    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="No permission")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$set": {"avatar": avatar, "lastUpdate": timestamp()}}
    )

    return {"state": 1}


@groupRouter.get('/getMembersInfo')
def getMembersInfo(group: str):
    '''
    获取群成员信息
    :param group: 群号
    :return: 群员uuid和lastUpdate
    '''
    members = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "user": 1}
    )

    membersInfo = [objID2info(i) for i in members["user"]]

    return {"users": membersInfo}


@groupRouter.post('/joinRequest')
async def joinRequest(group: str, joinText: str, user: UserSchema = Depends(getSelfInfo)):
    '''
    入群申请
    :param group: 群号
    :param joinText 申请信息
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "lastUpdate": 1, "question": 1, "owner": 1, "admin": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="该群不存在")

    time = timestamp()
    reqCollection = DB_CRUD(Database.ReqDB.value, group)
    admins = groupInfo["admin"] + [groupInfo["owner"]]

    exist = reqCollection.query(
        {"senderID": user["uuid"]},
        {"time": 1, "state": 1}
    )

    if exist and exist["state"] == 0 and int(timestamp()[:10]) - int(exist["time"][:10]) \
            < int(Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60):
        raise HTTPException(status_code=400, detail="申请中，等待审核")
    if groupInfo["_id"] in user["groups"]:
        raise HTTPException(status_code=400, detail="已经加入")

    sysMessage = SysMessageSchema(
        time=time,
        type="join",
        group=group,
        groupKey=groupInfo["lastUpdate"],
        senderID=user["uuid"],
        senderKey=user["lastUpdate"],
        payload=joinText,
    )

    requestMessage = RequestMsgSchema(
        time=time,
        type="join",
        group=group,
        groupKey=groupInfo["lastUpdate"],
        senderID=user["uuid"],
        senderKey=user["lastUpdate"],
        payload=joinText,
    )

    reqCollection.add(dict(requestMessage))

    for objID in admins:
        info = objID2info(objID)
        if info["uuid"] in SCM:
            await SCM.sending(info["uuid"], dict(sysMessage))

    return {"state": 1}


@groupRouter.get('/queryJoinRequest')
async def queryJoinRequest(group: str, user: UserSchema = Depends(getSelfInfo)):
    '''
    获取群验证消息，需要权限
    :param group: 群号
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "lastUpdate": 1, "question": 1, "owner": 1, "admin": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")
    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="仅群主/管理员可以获取")

    reqCollection = DB_CRUD(Database.ReqDB.value, group)
    messages = reqCollection.query(  # 获取在有效时间内的请求
        {"time": {"$gt": str(int(timestamp()) - Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60 * 1000 * 1000)}},
        {"_id": 0},
        True
    )

    for msg in messages:
        sysMessage = SysMessageSchema(
            time=msg["time"],
            type=msg["type"],
            group=group,
            groupKey=groupInfo["lastUpdate"],
            state=msg["state"],
            senderID=msg["senderID"],
            senderKey=msg["senderKey"],
            payload=msg["payload"]
        )
        await SCM.sending(user["uuid"], dict(sysMessage))


@groupRouter.post('/requestResponse')
async def requestResponse(group: str, time: str, verdict: bool, user: UserSchema = Depends(getSelfInfo)):
    '''
    验证群验证消息，需要管理员权限
    :param group: 群号
    :param time: 群验证发出时的时间
    :param verdict: True通过 False不通过
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "name": 1, "question": 1, "owner": 1, "admin": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")
    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="仅群主/管理员可以操作")
    if int(time) < int(timestamp()) - Miscellaneous.GROUP_REQUEST_EXPIRE_MINUTES.value * 60 * 1000 * 1000:
        raise HTTPException(status_code=400, detail="请求已过期")

    reqCollection = DB_CRUD(Database.ReqDB.value, group)
    requestInfo = reqCollection.query(
        {"time": time},
        {"_id": 0}
    )

    if not requestInfo:
        raise HTTPException(status_code=400, detail="该请求不存在")
    if requestInfo["state"] != RequestState.PENDING.value:
        raise HTTPException(status_code=403, detail="已被群主或其他管理员同意/拒绝")

    if verdict:
        currentState = (RequestState.ACCEPTED_BY_OWNER.value
                        if user["_id"] == groupInfo["owner"]
                        else RequestState.ACCEPTED_BY_ADMIN.value)

        # Collection.COLL_GRP.value.update(
        #     {"group": group},
        #     {"$push": {"user": user["_id"]}}
        # )
        # Collection.COLL_ACC.value.update(
        #     {"uuid": user["uuid"]},
        #     {"$push": {"groups": groupInfo["_id"]}}
        # )

        if requestInfo["senderID"] in SCM:
            sysMessage = SysMessageSchema(
                time=timestamp(),
                type="joined",
                group=group,
                state=currentState,
                payload=groupInfo["name"]
            )
            await SCM.sending(requestInfo["senderID"], dict(sysMessage))

    else:
        currentState = (RequestState.REJECTED_BY_OWNER.value
                        if user["_id"] == groupInfo["owner"]
                        else RequestState.REJECTED_BY_ADMIN.value)

    # reqCollection.update(
    #     {"time": time},
    #     {"$set": {"state": currentState}}
    # )

    sysMessage = SysMessageSchema(
        time=requestInfo["time"],
        type=requestInfo["type"],
        group=group,
        groupKey=requestInfo["groupKey"],
        state=currentState,
        senderID=requestInfo["senderID"],
        senderKey=requestInfo["senderKey"],
        payload=requestInfo["payload"]
    )

    admins = groupInfo["admin"] + [groupInfo["owner"]]
    for objID in admins:
        info = objID2info(objID)
        if info["uuid"] in SCM:
            await SCM.sending(info["uuid"], dict(sysMessage))

    return {"state": 1}


@groupRouter.post('/invite')
def inviteRequest(targetGroup: str, user: UserSchema = Depends(getSelfInfo)):
    '''
    入群邀请
    :param targetGroup: 目标群号
    :param user: 用户信息
    '''
    # groupConfig下邀请
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": targetGroup},
        {"_id": 1, "question": 1, "owner": 1, "admin": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=400, detail="群不存在")

    time = timestamp()

    if not groupInfo:
        pass

    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="仅群主/管理员可以邀请")


@groupRouter.post('/friendRequest')
def friendRequest(targetUser: str, user: UserSchema = Depends(getSelfInfo)):
    # 个人profile下发起
    pass
