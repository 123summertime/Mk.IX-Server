import hashlib
from datetime import datetime

from const import Collection


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def timestamp():
    return ("{:.6f}".format(datetime.now().timestamp())).replace(".", "")


def beforeSendCheck(userID, groupID, message):
    if message["type"] == "revoke":
        pass
