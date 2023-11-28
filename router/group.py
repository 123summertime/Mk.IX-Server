from uuid import uuid4

from const import Collection
from depend.depends import getUserInfo
from schema.user import UserSchema
from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

groupRouter = APIRouter(tags=['Group'])


@groupRouter.post("/makeGroup")
def makeGroup(name: str, question: str, answer: str, user: UserSchema = Depends(getUserInfo)):
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        owner=[user["uuid"], user["userName"]],
        question={question: answer},
        admin=dict(),
        user={user["uuid"]: user["userName"]},
    )

    Collection.COLL_GRP.value.add(dict(newGroup))
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$set": {f"groups.{groupID}": name}}
    )

    return {
        "groupID": groupID
    }


@groupRouter.post("/deleteGroup")
def deleteGroup(group: str, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")

    if groupInfo["owner"][0] == user["uuid"]:
        for member in groupInfo["user"]:
            Collection.COLL_ACC.value.update(
                {"uuid": member},
                {"$unset": {f"groups.{group}": ""}}
            )
        Collection.COLL_GRP.value.delete(
            {"group": group}
        )
    else:
        if user["uuid"] in groupInfo["admin"]:
            Collection.COLL_GRP.value.update(
                {"group": group},
                {"$unset": {f"admin.{groupInfo['admin']}": ""}}
            )
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$unset": {f"user.{groupInfo['user']}": ""}}
        )

    return {"state": 1}


@groupRouter.post("/deleteUser")
def deleteUser(who: str, group: str, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if user["uuid"] != groupInfo["owner"][0] and user["uuid"] not in groupInfo["admin"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if who == groupInfo["owner"][0] or who in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="Could not remove owner or admin")
    if user["uuid"] == who:
        raise HTTPException(status_code=403, detail="Could not remove yourself. Use deleteGroup")
    if who not in groupInfo["user"]:
        raise HTTPException(status_code=403, detail="Invalid user")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$unset": {f"user.{who}": ""}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": who},
        {"$unset": {f"groups.{group}": ""}}
    )
    return {"state": 1}


@groupRouter.post("/admin")
def admin(who: str, group: str, operation: bool, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "owner": 1, "admin": 1, "user": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if groupInfo["owner"][0] != user["uuid"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if groupInfo["owner"][0] == who:
        raise HTTPException(status_code=403, detail="Could not be owner and admin at the same time")

    if operation:
        if who not in groupInfo["user"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group {group}'s user")
        adminName = Collection.COLL_ACC.value.query(
            {"uuid": who},
            {"_id": 0, "userName": 1}
        )
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$set": {f"admin.{who}": adminName["userName"]}}
        )
    else:
        if who not in groupInfo["admin"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group {group}'s admin")
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$unset": {f"admin.{who}": ""}}
        )
    return {"state": 1}


@groupRouter.get("/joinRequest")
def joinRequest(group: str, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "question": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if group in user["groups"]:
        raise HTTPException(status_code=403, detail="Already Joined")

    return {"state": 1, "question": list(groupInfo["question"].keys())[0]}


@groupRouter.post("/join")
def join(group: str, answer: str, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "question": 1, "name": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if group in user["groups"]:
        raise HTTPException(status_code=403, detail="Already Joined")
    if answer != list(groupInfo["question"].values())[0]:
        raise HTTPException(status_code=401, detail="Incorrect answer")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$set": {f"user.{user['uuid']}": user["userName"]}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$set": {f"groups.{group}": groupInfo["name"]}}
    )

    return {"state": 1}


@groupRouter.get('/getInfo')
def getInfo(group: str, user: UserSchema = Depends(getUserInfo)):
    groupInfo = Collection.COLL_GRP.value.query(
        {"group": group},
        {"_id": 0, "name": 1, "group": 1, "avatar": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")

    return {"state": 1, "info": groupInfo}

