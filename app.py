import uvicorn
from fastapi import FastAPI
from router import login, ws, group
from fastapi.middleware.cors import CORSMiddleware


# uvicorn app:app --reload
app = FastAPI()
app.include_router(login.loginRouter)
app.include_router(ws.wsRouter)
app.include_router(group.groupRouter)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
