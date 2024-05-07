import hashlib
from typing import Union, List

from gridfs import GridFS

from public.const import Database
from schema.group import GroupSchema
from schema.storage import StorageSchema, RequestMsgSchema, FileStorageSchema
from schema.user import UserSchema

client = Database.CLIENT.value


class DB_CRUD():
    def __init__(self, name, collectionName, schema):
        self.schema = schema
        try:
            self._collection = client[name][collectionName]
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


class GridFS_CRUD():
    def __init__(self, name):
        self.db = client[name]
        self.fs = GridFS(self.db)

    def add(self, file, filename, contentType, group):
        hashInstance = hashlib.sha256()
        hashInstance.update(file)
        hashValue = hashInstance.hexdigest()

        self.fs.put(file, filename=filename, hash=hashValue, type=contentType)
        return hashValue

    def delete(self, hashValue):
        file = self.db.fs.files.find_one(
            {'hash': hashValue}
        )

        if file:
            self.fs.delete(file['_id'])

    def query(self, hashValue) -> FileStorageSchema | None:
        file = self.db.fs.files.find_one(
            {'hash': hashValue}
        )

        if not file:
            return None

        info = {
            "name": file['filename'],
            "type": file['type'],
            "file": self.fs.get(file['_id']).read()
        }

        return FileStorageSchema.parse_obj(info)


