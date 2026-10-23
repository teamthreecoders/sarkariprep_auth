
from fastapi import APIRouter, status, Response, Request, Cookie, BackgroundTasks
from fastapi import Depends,Body,Header
from core.config import AllowedTokenPurpose
from exceptions.token import InvalidTokenException
from services.auth import AuthServices
from core.database import DBConn
from schemas.auth import SignupRequestPayload, SetPasswordRequestPayload, LoginRequestPayload, \
    ForgotPasswordRequestPayload, GetCurrentUserRequestPayload, LogOutResponsePayload, RefreshTokenRequestPayload
from schemas.otp import OTPVerificationRequestPayload
from services.token import AccessTokenService
from core.logger import logger


def get_db_conn():
    """

    :return: DBConnection
    """
    with DBConn() as dbConn:
        yield dbConn

# token validator
def auth_token_validate(purpose):
    def validator(
            Authorization: str = Header(),
            dbConn=Depends(get_db_conn, use_cache=True)
    ):
        from exceptions.token import InvalidTokenException, ExpiredTokenException

        if not Authorization.strip().startswith("Bearer "):
            raise InvalidTokenException

        token = Authorization.strip().split()[-1]
        try:
            payload = AccessTokenService.validate_token(dbConn, token=token, purpose=purpose)
            return payload
        except Exception as err:
            logger.exception("Token Authentication Failed!")
            raise ExpiredTokenException
    return validator


route = APIRouter(prefix="/v1/auth", tags=["AUTH"])

@route.post("/me",status_code=status.HTTP_200_OK)
def get_current_user(backgroundTasks:BackgroundTasks,
        dbConn:DBConn = Depends(get_db_conn,use_cache=True),
        Authorization:str = Header(None)
):
    logger.info(Authorization)
    if not Authorization or not Authorization.strip().startswith("Bearer "):
        raise InvalidTokenException
    token = Authorization.split()[-1]
    auth_service = AuthServices(dbConn,backgroundTasks=backgroundTasks)
    response = auth_service.get_current_user(request=GetCurrentUserRequestPayload(token=token))
    return response

@route.post('/signup',status_code=status.HTTP_201_CREATED)
def signup(backgroundTasks:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn,use_cache=True), payload:SignupRequestPayload = Body(title='Request payload', description='abcd')):
    auth_services = AuthServices(dbConn=dbConn, backgroundTasks=backgroundTasks)
    response = auth_services.signup(request=payload)
    return response

@route.post("/signup/set-password",status_code=status.HTTP_201_CREATED)
def set_password(backgroundTasks:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn,use_cache=True),
                payload:SetPasswordRequestPayload = Body(title="Password setup", description="abcd"),
                token_payload = Depends(auth_token_validate(AllowedTokenPurpose.SIGN_UP))
                ):
    auth_services = AuthServices(dbConn=dbConn, backgroundTasks=backgroundTasks)
    response = auth_services.set_password(request=payload,token_payload=token_payload)
    return response

@route.post("/magic_link/login",status_code=status.HTTP_200_OK, deprecated=True,tags=['login'])
def login(backgroundTask:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn,use_cache=True), payload:LoginRequestPayload = Body(title="Login Data")):
    auth_service = AuthServices(dbConn, backgroundTask)
    response = auth_service.login(request=payload,via='magic_link')
    return response

@route.post("/otp/login",status_code=status.HTTP_200_OK,tags=['login'])
def login(backgroundTask:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn,use_cache=True), payload:LoginRequestPayload = Body(title="Login Data")):
    auth_service = AuthServices(dbConn, backgroundTask)
    response = auth_service.login(request=payload,via='otp')
    return response

@route.post("/otp/login/2fa_verify", status_code=status.HTTP_200_OK)
def twoFAlogin(backgroundTasks:BackgroundTasks, response:Response, dbConn:DBConn = Depends(get_db_conn,use_cache=True), payload:OTPVerificationRequestPayload = Body()):

    logger.info(payload)
    auth_services = AuthServices(dbConn, backgroundTasks)
    data =  auth_services.login_otp_verification(payload=payload)
    response.set_cookie("Authorization",f'Bearer {data.data.token}')
    return data

@route.post("/refresh", status_code=status.HTTP_200_OK)
def refresh(backgroundTasks:BackgroundTasks, response:Response, dbConn:DBConn = Depends(get_db_conn,use_cache=True), payload:RefreshTokenRequestPayload = Body()):
    auth_services = AuthServices(dbConn, backgroundTasks)
    data = auth_services.refresh_session(payload=payload)
    response.set_cookie("Authorization",f'Bearer {data.data.token}')
    return data

@route.post("/forgot-password",status_code=status.HTTP_202_ACCEPTED)
def forgot_password(backgroundTasks:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn), payload:ForgotPasswordRequestPayload = Body()):
    auth_services = AuthServices(dbConn,backgroundTasks)
    response  = auth_services.forgot_password(payload=payload)
    return response

@route.post("/reset-password",status_code=status.HTTP_200_OK)
def reset_password(backgroundTasks:BackgroundTasks, dbConn:DBConn = Depends(get_db_conn), payload:SetPasswordRequestPayload = Body(),
                   token_payload = Depends(auth_token_validate(AllowedTokenPurpose.PASSWORD_RESET))
                   ):
    auth_services = AuthServices(dbConn=dbConn, backgroundTasks=backgroundTasks)
    response = auth_services.reset_password(request=payload,token_payload=token_payload)
    return response

@route.delete("/logout",status_code=status.HTTP_200_OK)
def logout(response:Response, dbConn:DBConn = Depends(get_db_conn, use_cache=True), Authorization:str = Header(None),
           payload:RefreshTokenRequestPayload | None = Body(default=None)):
    if Authorization and Authorization.strip().startswith("Bearer "):
        token = Authorization.strip().split()[-1]
        try:
            payload = AccessTokenService.validate_token(dbConn, token=token, purpose=AllowedTokenPurpose.LOGIN_SESSION)
            AccessTokenService.mark_token_as_used(dbConn, token_id=payload['token_id'])
            dbConn.commit()
        except Exception:
            pass
    if payload and payload.refresh_token:
        # Also kill the refresh token so the session can't be renewed after logout.
        try:
            claims = AccessTokenService.validate_token(dbConn, token=payload.refresh_token, purpose=AllowedTokenPurpose.REFRESH_TOKEN)
            AccessTokenService.mark_token_as_used(dbConn, token_id=claims['token_id'])
            dbConn.commit()
        except Exception:
            pass
    response.delete_cookie("Authorization")
    return LogOutResponsePayload().model_dump()