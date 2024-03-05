from typing import List
from uuid import uuid4

from const import Collection, Miscellaneous
from depend.depends import getUserInfo
from utils.helper import timestamp
from schema.user import UserSchema
from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

groupRouter = APIRouter(tags=['Group'])

# TODO: 创建群时新建ws
# TODO: 删除/退出/踢出群时断开ws


@groupRouter.post("/makeGroup")
def makeGroup(name: str, question: str, answer: str, user: UserSchema = Depends(getUserInfo)):
    '''
    创建群
    :param name: 群名
    :param question: 入群问题
    :param answer: 入群问题答案
    :param user: 用户信息
    :return: 创建的群的uuid
    '''
    groupID = str(uuid4().int)[::4]
    ownerObjID = Collection.COLL_ACC.value.query(
        {"uuid": user["uuid"]},
        {"_id": 1}
    )["_id"]

    newGroup = GroupSchema(
        group=groupID,
        name=name,
        avatar=Miscellaneous.DEFAULT_AVATAR.value,
        lastUpdate=timestamp(),
        owner=ownerObjID,
        question=[{"question": question, "answer": answer}],
        admin=[],
        user=[ownerObjID],
    )

    groupObjID = Collection.COLL_GRP.value.add(dict(newGroup)).inserted_id
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$push": {"groups": groupObjID}}
    )

    return {
        "groupID": groupID
    }


@groupRouter.post("/deleteGroup")
def deleteGroup(group: str, user: UserSchema = Depends(getUserInfo)):
    '''
    退出/解散群
    :param group: 群号
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")

    # 为群主时解散 其余成员为退出
    if groupInfo["owner"] == user["_id"]:
        for objID in groupInfo["user"]:
            Collection.COLL_ACC.value.update(
                {"_id": objID},
                {"$pull": {"groups": groupInfo["_id"]}}
            )
        Collection.COLL_GRP.value.delete(
            {"group": group}
        )
    else:
        if user["_id"] in groupInfo["admin"]:
            Collection.COLL_GRP.value.update(
                {"group": group},
                {"$pull": {"admin": user["_id"]}}
            )
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$pull": {"user": user["_id"]}}
        )

    return {"state": 1}


@groupRouter.post("/deleteUser")
def deleteUser(who: str, group: str, user: UserSchema = Depends(getUserInfo)):
    '''
    踢出群
    :param who: 被执行对象
    :param group: 群号
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "owner": 1, "admin": 1, "user": 1}
    )
    whoInfo = Collection.COLL_ACC.value.query(
        {"uuid": who},
        {"_id": 1}
    )

    if not who or whoInfo["_id"] not in groupInfo["user"]:
        raise HTTPException(status_code=403, detail="Invalid user")
    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if user["_id"] != groupInfo["owner"] and user["_id"] not in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="No permissions")
    if whoInfo["_id"] == groupInfo["owner"] or whoInfo["_id"] in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="Could not remove owner or admin")
    if user["_id"] == whoInfo["_id"]:
        raise HTTPException(status_code=403, detail="Could not remove yourself")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$pull": {"user": whoInfo["_id"]}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": who},
        {"$pull": {"groups": groupInfo["_id"]}}
    )

    return {"state": 1}


@groupRouter.post("/admin")
def admin(who: str, group: str, operation: bool, user: UserSchema = Depends(getUserInfo)):
    '''
    增加/减少管理员
    :param who: 被执行对象
    :param group: 群号
    :param operation: True成为管理员 False取消管理员
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "owner": 1, "admin": 1, "user": 1}
    )
    whoInfo = Collection.COLL_ACC.value.query(
        {"uuid": who},
        {"_id": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if groupInfo["owner"] != user["_id"]:
        raise HTTPException(status_code=403, detail="No permissions")
    if groupInfo["owner"] == whoInfo["_id"]:
        raise HTTPException(status_code=403, detail="Invalid operation")

    if operation:
        if whoInfo["_id"] not in groupInfo["user"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group {group}'s user")
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$push": {"admin": whoInfo["_id"]}}
        )
    else:
        if whoInfo["_id"] not in groupInfo["admin"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group {group}'s admin")
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$pull": {"admin": whoInfo["_id"]}}
        )

    return {"state": 1}


@groupRouter.get("/joinRequest")
def joinRequest(group: str, user: UserSchema = Depends(getUserInfo)):
    '''
    获取入群问题
    :param group: 群号
    :param user: 用户信息
    :return: 包含入群问题的List
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "question": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if groupInfo["_id"] in user["groups"]:
        raise HTTPException(status_code=403, detail="Already Joined")

    return [i["question"] for i in groupInfo["question"]]


@groupRouter.post("/join")
def join(group: str, answer: List[str], user: UserSchema = Depends(getUserInfo)):
    '''
    加入群聊
    :param group: 群号
    :param answer: 入群问题答案
    :param user: 用户信息
    '''
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 1, "question": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if groupInfo["_id"] in user["groups"]:
        raise HTTPException(status_code=403, detail="Already Joined")
    if answer != [i["answer"] for i in groupInfo["question"]]:
        raise HTTPException(status_code=401, detail="Incorrect answer")

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

    def objID2info(objID):
        info = Collection.COLL_ACC.value.query(
            {"_id": objID},
            {"_id": 0, "uuid": 1, "lastUpdate": 1}
        )
        return info

    return {
        "owner": objID2info(adminInfo["owner"]),
        "admin": [objID2info(i) for i in adminInfo["admin"]]
    }



