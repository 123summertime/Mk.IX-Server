from typing import Any
import pymongo

client = pymongo.MongoClient("localhost", 27017, maxPoolSize=50)

class DB_CRUD():
    collection: Any

    def __init__(self, dbName, collectionName):
        try:
            self.collection = client[dbName][collectionName]
        except:
            raise NameError("Invalid DB or collection name")

    def add(self, kv):
        _id = self.collection.insert_one(kv).inserted_id
        return {
            "success": True if _id else False
        }

    def delete(self, kv):
        self.collection.delete_one(kv)

    def update(self, qkv, ukv):
        self.collection.update_one(qkv, ukv)

    def query(self, kv, ignore = {}):
        if not ignore:
            return self.collection.find_one(kv)
        else:
            return self.collection.find_one(kv, ignore)
