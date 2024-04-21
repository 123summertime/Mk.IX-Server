from typing import Any, Union, List, Dict

from schema.user import UserSchema
from schema.group import GroupSchema
from schema.storage import StorageSchema, RequestMsgSchema

import pymongo

client = pymongo.MongoClient("localhost", 27017, maxPoolSize=50)


class DB_CRUD():
    def __init__(self, dbName, collectionName, schema):
        self.schema = schema
        try:
            self._collection = client[dbName][collectionName]
        except Exception:
            raise NameError("Invalid DB or collection name")

    def add(self, kv, many=False):
        if many:
            return self._collection.insert_many(kv)
        else:
            return self._collection.insert_one(kv)

    def delete(self, kv, many=False):
        if many:
            return self._collection.delete_many(kv)
        else:
            return self._collection.delete_one(kv)

    def update(self, qkv, ukv):
        return self._collection.update_one(qkv, ukv)

    def query(self, kv, ignore={}) -> Union[GroupSchema, UserSchema, StorageSchema, RequestMsgSchema, None]:
        info = self._collection.find_one(kv, ignore)
        if not info:
            return None
        return self.schema.parse_obj(info)

    def queryMany(self, kv, ignore) -> List[Union[GroupSchema, UserSchema, StorageSchema, RequestMsgSchema]] | None:
        info = self._collection.find(kv, ignore)
        if not info:
            return None
        return [self.schema.parse_obj(i) for i in info]
