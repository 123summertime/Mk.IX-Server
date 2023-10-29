from fastapi import FastAPI, APIRouter

groupRouter = APIRouter(tags=['group'])

@groupRouter.post("/makeGroup")
def makeGroup():
    pass