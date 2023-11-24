from uuid import uuid4

from const import Collection
from depend.depends import getUserInfo
from schema.user import UserSchema
from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

groupRouter = APIRouter(tags=['Group'])


@groupRouter.post("/makeGroup")
def makeGroup(name: str, groupAvatar: str, question: str, answer: str, user: UserSchema = Depends(getUserInfo)):
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        owner=user["uuid"],
        avatar=groupAvatar,
        question={question: answer},
        admin=[],
        user=[user["uuid"]],
    )

    Collection.COLL_GRP.value.add(dict(newGroup))
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$addToSet": {"groups": groupID}}
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

    if groupInfo["owner"] == user["uuid"]:
        for member in groupInfo["user"]:
            Collection.COLL_ACC.value.update(
                {"uuid": member},
                {"$pull": {"groups": group}}
            )
        Collection.COLL_GRP.value.delete(
            {"group": group}
        )
    else:
        if user["uuid"] in groupInfo["admin"]:
            groupInfo["admin"].remove(user["uuid"])
        groupInfo["user"].remove(user["uuid"])
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$set": {"admin": groupInfo["admin"], "user": groupInfo["user"]}}
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
    if user["uuid"] != groupInfo["owner"] and user["uuid"] not in groupInfo["admin"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if who == groupInfo["owner"] or who in groupInfo["admin"]:
        raise HTTPException(status_code=403, detail="Could not remove owner or admin")
    if user["uuid"] == who:
        raise HTTPException(status_code=403, detail="Could not remove yourself. Use deleteGroup")
    if who not in groupInfo["user"]:
        raise HTTPException(status_code=403, detail="Invalid user")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$pull": {"user": who}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": who},
        {"$pull": {"groups": group}}
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
    if groupInfo["owner"] != user["uuid"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if groupInfo["owner"] == who:
        raise HTTPException(status_code=403, detail="Could not be owner and admin at the same time")

    if operation:
        if who not in groupInfo["user"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group{group}'s user")
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$addToSet": {"admin": who}}
        )
    else:
        if who not in groupInfo["admin"]:
            raise HTTPException(status_code=403, detail=f"{who} is not group{group}'s admin")
        Collection.COLL_GRP.value.update(
            {"group": group},
            {"$pull": {"admin": who}}
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
        {"_id": 0, "question": 1}
    )

    if not groupInfo:
        raise HTTPException(status_code=403, detail="Invalid group")
    if group in user["groups"]:
        raise HTTPException(status_code=403, detail="Already Joined")
    if answer != list(groupInfo["question"].values())[0]:
        raise HTTPException(status_code=401, detail="Incorrect answer")

    Collection.COLL_GRP.value.update(
        {"group": group},
        {"$addToSet": {"user": user["uuid"]}}
    )
    Collection.COLL_ACC.value.update(
        {"uuid": user["uuid"]},
        {"$addToSet": {"groups": group}}
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

