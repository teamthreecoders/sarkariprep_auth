from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse

from core.config import AllowedTokenPurpose
from core.database import DBConn
from core.logger import logger
from services.token import AccessTokenService

router = APIRouter(prefix="/pages/auth", tags=['AUTH PAGE'])
VALID_PURPOSES = {AllowedTokenPurpose.SIGN_UP,AllowedTokenPurpose.PASSWORD_RESET}

def _load_html(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


class HTMLException(HTTPException):
    def __init__(self, html_path: str, status_code: int):
        self.html_path = html_path
        super().__init__(status_code=status_code)

def validate_token(purpose, file_name):
    def wrapper(challenge_token: str = Query()) :
        try:
            logger.info(challenge_token)
            payload = AccessTokenService.validate_token(token=challenge_token,dbConn=DBConn(),purpose=purpose)
            logger.info(f"PAYLOAD::{payload}")

            if payload.get("purpose") not in VALID_PURPOSES:
                return HTMLResponse(content=_load_html('templates/webpage/unauthorized.html'),status_code=401)
        except Exception as err:
            logger.exception(err.args)
            return HTMLResponse(content=_load_html("templates/webpage/token-expire.html"), status_code=401)
        return HTMLResponse(
            content=_load_html(f"templates/webpage/{file_name}"),
            status_code=200,
        )
    return wrapper

@router.get("/set-password")
async def set_password_page(page: str = Depends(validate_token(AllowedTokenPurpose.SIGN_UP,'set_password.html'))):
    # Initial password setup
    return page

@router.get("/reset-password")
async def reset_password(page: str = Depends(validate_token(AllowedTokenPurpose.PASSWORD_RESET,'reset_password.html'))):
    # Password Reset
    return page