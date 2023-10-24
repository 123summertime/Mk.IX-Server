import hashlib

def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()
