import hashlib
from datetime import datetime


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def timestamp():
    return ("{:.6f}".format(datetime.now().timestamp())).replace(".", "")
