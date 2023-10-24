# import pymongo
# import pprint
#
# client = pymongo.MongoClient("localhost", 27017)
#
# db = client.test1
#
# coll = db.coll1
#
# # t = coll.insert_one({
# #     "name": "OP3",
# #     "特征": "忘源生的"
# # }).inserted_id
# # print(t)
# # for i in range(100):
# #     for p in coll.find({"name": "OP2"}):
# #         pprint.pprint(p)
#
# client.close()
#
# # ----->
#
# from fastapi import FastAPI
# import uvicorn
#
# app = FastAPI()
# # XX,启动!
# # uvicorn app:app --reload
#
# @app.get("/")
# async def index():
#     return {}
#
# # 动态路由及查询参数
# @app.get("/{id}")
# async def index(id, x:str = "10"): # x<-是URL传入的参数 =默认值 :类型
#     return {}
#
#
# # post请求体
# from pydantic import BaseModel
# class Blog(BaseModel):
#     title: str
#     body: str
# @app.post("/post")
# async def posting(req: Blog):
#     return req
#
# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=17900)