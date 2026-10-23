from argon2 import PasswordHasher
from core.logger import logger
def hashSecrets(secret:str):
    ph = PasswordHasher()
    return ph.hash(secret)

def matchSecrets(*,secret:str,hashed_secret:str) ->bool:
    ph = PasswordHasher()
    try:
        return ph.verify(hashed_secret, secret)
    except Exception as err:
        logger.exception(err.args)
        return False