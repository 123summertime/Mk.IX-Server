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
        try:
            for member in group["user"]:
                joined = Collection.COLL_ACC.value.query(
                    {"uuid": member},
                    {"_id": 0, "groups": 1}
                )
                joined.remove(groupID)

                Collection.COLL_ACC.value.update(
                    {"uuid": member},
                    {"$set": {"groups": joined}}
                )

            Collection.COLL_GRP.value.delete(
                {"group": groupID}
            )
            return {"state": 1}
        except Exception:
            return {"state": 0}
    # 退群
    else:
        try:
            if user["uuid"] in group["admin"]:
                group["admin"].remove(user["uuid"])
            group["user"].remove(user["uuid"])
            Collection.COLL_GRP.value.update(
                {"group": groupID},
                {"$set": {"admin": group["admin"],"user": group["user"]}}
            )
            return {"state": 1}
        except Exception:
            return {"state": 0}




