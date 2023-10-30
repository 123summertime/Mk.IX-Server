from uuid import uuid4

from schema.group import GroupSchema

from fastapi import FastAPI, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

groupRouter = APIRouter(tags=['group'])

@groupRouter.post("/makeGroup")
def makeGroup(name: str):
    newGroup = GroupSchema(
        group= str,
        name = name,
        owner = str,
        admin = [],
        user = [],
    )