from uuid import uuid4

from const import Collection
from depend.depends import getUserInfo
from schema.user import UserSchema
from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer

groupRouter = APIRouter(tags=['Group'])


@groupRouter.post("/makeGroup")
def makeGroup(name: str, user: UserSchema = Depends(getUserInfo)):
    groupID = str(uuid4().int)[::4]
    newGroup = GroupSchema(
        group=groupID,
        name=name,
        owner=user["uuid"],
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
def deleteGroup(groupID: str, user: UserSchema = Depends(getUserInfo)):
    group = Collection.COLL_GRP.value.query(
        {"group": groupID},
        {"_id": 0, "owner": 1, "admin": 1, "user": 1})

    # 解散
    if group["owner"] == user["uuid"]:
        Collection.COLL_GRP.value.delete(
            {"group": groupID}
        )
        for member in group["user"]:
            Collection.COLL_ACC.value.update(
                {"uuid": member},
                {"$pull": {"groups": groupID}}
            )
    # 退群
    else:
        if user["uuid"] in group["admin"]:
            Collection.COLL_GRP.value.update(
                {"group": groupID},
                {"$pull": {"admin": user["uuid"]}}
            )
        Collection.COLL_GRP.value.update(
            {"group": groupID},
            {"$pull": {"user": user["uuid"]}}
        )





