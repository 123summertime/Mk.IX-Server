from uuid import uuid4

from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter
from fastapi.security import OAuth2PasswordBearer

groupRouter = APIRouter(tags=['Group'])

@groupRouter.post("/makeGroup")
def makeGroup(name: str):
    newGroup = GroupSchema(
        group= str,
        name = name,
        owner = str,
        admin = [],
        user = [],
    )