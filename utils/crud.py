import hashlib
from typing import Union, List
from datetime import datetime, timezone

from gridfs import GridFS

from public.const import Database
from schema.group import GroupSchema
from schema.storage import StorageSchema, RequestMsgSchema, FileStorageSchema
from schema.user import UserSchema
from utils.helper import timestamp

client = Database.CLIENT.value


class DB_CRUD():
    def __init__(self, name, collectionName, schema):
        self._schema = schema
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
        return self._schema.parse_obj(info)

    def queryMany(self, kv, ignore={}) -> List[Union[GroupSchema, UserSchema, StorageSchema, RequestMsgSchema]] | None:
        info = self._collection.find(kv, ignore)
        if not info:
            return None
        return [self._schema.parse_obj(i) for i in info]


class GridFS_CRUD():
    def __init__(self, name):
        self._db = client[name]
        self._fs = GridFS(self._db)

    def add(self, file, filename, contentType, group):
        hashInstance = hashlib.sha256()
        hashInstance.update(file)
        hashcode = hashInstance.hexdigest()

        exist = self._db.fs.files.find_one(
            {'hash': hashcode}
        )
        if exist:
            self.update(hashcode, {"uploadDate": datetime.now(timezone.utc)})
        else:
            self._fs.put(file, filename=filename, hash=hashcode, type=contentType, group=group)

        return hashcode

    def delete(self, hashcode):
        file = self._db.fs.files.find_one(
            {'hash': hashcode}
        )
        if file:
            self._fs.delete(file['_id'])

    def query(self, hashcode) -> FileStorageSchema | None:
        file = self._db.fs.files.find_one(
            {'hash': hashcode}
        )
        if not file:
            return None

        info = {
            "name": file['filename'],
            "type": file['type'],
            "group": file['group'],
            "file": self._fs.get(file['_id']).read()
        }

        return FileStorageSchema.parse_obj(info)

    def update(self, hashcode, ukv):
        file = self._db.fs.files.find_one(
            {'hash': hashcode}
        )
        if not file:
            return None

        self._db.fs.files.update_one(
            {'_id': file["_id"]},
            {'$set': ukv}
        )


class CRUD_helpers():
    @staticmethod
    def objectIDtoInfo(objID) -> UserSchema:
        info = ACCOUNT.query(
            {"_id": objID},
            {"_id": 0, "uuid": 1, "lastUpdate": 1}
        )
        return info


ACCOUNT = DB_CRUD(Database.USER_DB.value, "Account", UserSchema)
GROUP = DB_CRUD(Database.USER_DB.value, "Group", GroupSchema)
FS = GridFS_CRUD("File")
