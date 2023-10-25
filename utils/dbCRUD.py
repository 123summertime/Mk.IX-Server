from typing import Any, Union, List, Dict

import pymongo


client = pymongo.MongoClient("localhost", 27017, maxPoolSize=50)

class DB_CRUD():
    def __init__(self, dbName, _collectionName):
        try:
            self._collection = client[dbName][_collectionName]
        except:
            raise NameError("Invalid DB or collection name")

    def add(self, kv, many = False):
        if many:
            self._collection.insert_many(kv)
        else:
            self._collection.insert_one(kv)

    def delete(self, kv, many = False):
        if many:
            self._collection.delete_many(kv)
        else:
            self._collection.delete_one(kv)

    def update(self, qkv, ukv):
        self._collection.update_one(qkv, ukv)

    def query(self, kv, ignore = {}, many = False):
        if many:
            return self._collection.find(kv, ignore)
        else:
            return self._collection.find_one(kv, ignore)

offlineMsg = DB_CRUD("UserInfo", "OfflineMsg").query({
            "uuid": "1738032049",
            "group": "10000"
        }, {
            "_id": 0,
            "uuid": 0,
            "group": 0
        }, True)
