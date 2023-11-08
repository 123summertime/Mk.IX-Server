import pymongo

client = pymongo.MongoClient("localhost", 27017, maxPoolSize=50)


class DB_CRUD():
    def __init__(self, dbName, _collectionName):
        try:
            self._collection = client[dbName][_collectionName]
        except Exception:
            raise NameError("Invalid DB or collection name")

    def add(self, kv, many=False, session=None):
        if many:
            self._collection.insert_many(kv, session=session)
        else:
            self._collection.insert_one(kv, session=session)

    def delete(self, kv, many=False, session=None):
        if many:
            self._collection.delete_many(kv, session=session)
        else:
            self._collection.delete_one(kv, session=session)

    def update(self, qkv, ukv, session=None):
        self._collection.update_one(qkv, ukv, session=session)

    def query(self, kv, ignore={}, many=False, session=None):
        if many:
            return self._collection.find(kv, ignore)
        else:
            return self._collection.find_one(kv, ignore)


def transaction(operations):
    '''
    Element: [Collection.CRUD_operation, [arguments]]
    '''
    with client.start_session() as session:
        with session.start_transaction():
            for func, op in operations:
                func(*op, session=session)
                raise Exception("玩原神导致的")
