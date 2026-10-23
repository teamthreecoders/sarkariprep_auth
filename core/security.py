from datetime import timedelta
from datetime import datetime,UTC
from jwt import encode,decode
from core.config import JWTConfig
from core.logger import logger
from jwt.exceptions import ExpiredSignatureError


def create_access_token(payload: dict, *,
                        secret_key:str =  JWTConfig.SECRET_KEY,
                        algorithm:str = JWTConfig.ALGORITHM,
                        access_token_expire_min:int = JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES) -> str:

    """
    Creates a JWT access token with the provided payload and an expiration time.
    Args:
        payload (dict): A dictionary containing the data to be included in the token payload.
        secret_key (str): The secret key used to sign the token. Default is JWTConfig.SECRET_KEY.(ENV variable)
        algorithm (str): The algorithm used to sign the token. Default is JWTConfig.ALGORITHM.(ENV variable)
        access_token_expire_min (int): The expiration time for the access token in minutes. Default is JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES.(ENV variable)
    Returns:
        str: A JWT access token as a string.
    Raises:
        Exception: If there is an error during token creation, an exception is raised.
    """
    try:
        to_encode = payload.copy()
        expire = datetime.now(UTC) + timedelta(minutes=access_token_expire_min)
        to_encode.update({"exp": expire})
        encoded_jwt = encode(to_encode, secret_key, algorithm=algorithm)
        logger.info(encoded_jwt)
        return encoded_jwt

    except Exception as error:
        logger.error(f"❌ Failed to create access token!\nCAUSE::{error}")
        raise


def create_refresh_token(data: dict) -> str:
    try:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=JWTConfig.REFRESH_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = encode(to_encode, JWTConfig.SECRET_KEY, algorithm=JWTConfig.ALGORITHM)
        return encoded_jwt

    except Exception as error:
        logger.error(f"❌ Failed to create refresh token!\nCAUSE::{error}")
        raise


def verify_token(token: str) -> dict:
    """
    Verifies a JWT token and returns the decoded payload if the token is valid.

    Args:
        token (str): The JWT token to be verified.
    Returns:
        dict: The decoded payload of the token if it is valid.
    Raises:
        Exception: If the token is invalid or expired, an exception is raised.
    """
    try:
        decoded_token = decode(token, JWTConfig.SECRET_KEY, algorithms=[JWTConfig.ALGORITHM])
        return decoded_token

    except ExpiredSignatureError as error:
        logger.error("Token expired")
        raise

    except Exception as error:
        logger.error(f"❌ Failed to verify token!\nCAUSE::{error}")
        raise
