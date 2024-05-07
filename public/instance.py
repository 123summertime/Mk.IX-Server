from enum import Enum

from public.const import Database
from schema.group import GroupSchema
from schema.user import UserSchema
from utils.dbCRUD import DB_CRUD, GridFS_CRUD


class Collection(Enum):
    ACCOUNT = DB_CRUD(Database.USER_DB.value, "Account", UserSchema)
    GROUP = DB_CRUD(Database.USER_DB.value, "Group", GroupSchema)
    FS = GridFS_CRUD("File")
