from dataclasses import dataclass
import dotenv
import os
from enum import StrEnum

# load .env file
dotenv.load_dotenv()

class DBConfig:
    """
    Database related configuration
    HOST
    PORT
    USER
    PASSWORD
    DATABASE
    """
    HOST:str = os.environ.get("PGHOST")
    PORT:int = int(os.environ.get("PGPORT", 5432))
    USER:str = os.environ.get("PGUSER",'user')
    PASSWORD:str = os.environ.get("PGPASSWORD", 'password')
    DATABASE:str = os.environ.get("PGDATABASE",'database')
    SSLMODE:str = os.environ.get("PGSSLMODE",'ssl')
    CHANNELBINDING:str = os.environ.get("PGCHANNELBINDING",'require')
    CONN_URL:str = os.environ.get("PGCONNURL",'postgresql://')
    CONNECT_TIMEOUT:int = 10

@dataclass(frozen = True)
class SMTPConfig:
    """
    SMTP related configuration
    EMAIL
    PASSWORD
    HOST
    PORT
    TIMEOUT
    """
    EMAIL:str = os.environ.get("SMTPEMAIL")
    PASSWORD:str = os.environ.get("SMTPPASSWORD")
    HOST:str = os.environ.get("SMTPHOST")
    PORT:int = int(os.environ.get("SMTPPORT", 587))
    TIMEOUT:int = 10

class JWTConfig:
    """
    JWT related configuration
    SECRET_KEY
    ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_MINUTES
    """
    SECRET_KEY:str = os.environ.get("JWTSECRETKEY")
    ALGORITHM:str = os.environ.get("JWTALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES:int = int(os.environ.get("JWTACCESSTOKENEXPIRATIONMINUTES", 15))
    CHALLENGE_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("JWTCHALLENGETOKENEXPIRATIONMINUTES", 30))
    OTP_EXPIRE_MINUTES:int = int(os.environ.get("JWTOTPTOKENEXPIRATIONMINUTES", 30))
    REFRESH_TOKEN_EXPIRE_MINUTES:int = int(os.environ.get("JWTREFRESHTOKENEXPIRATIONMINUTES", 43200))  # 30 days

EMAIL_VERIFICATION_BASEURL ='https://apiauthsarkariprep.vercel.app/pages/auth'

# allowed Token Purpose
class AllowedTokenPurpose(StrEnum):
    LOGIN_SESSION = "LOGIN_SESSION"
    REFRESH_TOKEN = "REFRESH_TOKEN"
    LOGIN_2FA_MAGIC_URL = "LOGIN_2FA_MAGIC_URL"
    LOGIN_2FA_OTP = "LOGIN_2FA_OTP"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    SIGN_UP = "SIGN_UP"
