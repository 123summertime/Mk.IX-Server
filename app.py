import uvicorn
from fastapi import FastAPI, Request
from router import user, ws, group
from fastapi.middleware.cors import CORSMiddleware
from utils.helper import cleaner
from middleware.middleware import log500Error
from apscheduler.schedulers.background import BackgroundScheduler


# uvicorn app:app --reload
app = FastAPI()
app.include_router(user.userRouter)
app.include_router(ws.wsRouter)
app.include_router(group.groupRouter)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log500Error)


# 定时清理过期文件/消息/请求
scheduler = BackgroundScheduler()
scheduler.add_job(cleaner, 'cron', hour=3, minute=0)
scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
