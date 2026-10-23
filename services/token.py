from core.config import AllowedTokenPurpose, JWTConfig
from core.database import DBConn
from core.security import create_access_token, verify_token
from schemas.token import AuthTokenPayload, AuthTokenPayload, AuthTokenPayload
from repositories.token_repository import TokenRepository
from jwt.exceptions import InvalidTokenError
from core.logger import logger
from uuid import uuid4


class AccessTokenService:
    @staticmethod
    def _create_and_store_token(dbConn:DBConn,*,token_payload):
        # TODO:: Will make a general helper method to generate token
        pass

    @staticmethod
    def create_for_set_password(dbConn:DBConn,*, token_id:str ,email, user_id, purpose)-> str | None:
        payload = AuthTokenPayload(
            token_id = token_id,
            email=email,
            user_id=user_id,
            purpose=purpose
        )
        token = create_access_token(payload.model_dump(), access_token_expire_min=JWTConfig.CHALLENGE_TOKEN_EXPIRE_MINUTES)
        response = TokenRepository.add_to_token_log(dbConn=dbConn, token_id=token_id, user_id=user_id, email=email,
                                                    token=token, purpose=purpose,exp_interval_min = JWTConfig.CHALLENGE_TOKEN_EXPIRE_MINUTES)
        logger.info(f"Response:{response}")
        if response and response > 0:
            logger.info("Token added to log")
            return token
        return None


    @staticmethod
    def mark_token_as_used(dbConn:DBConn,*,token_id):
        return TokenRepository.update_token_log(dbConn,token_id = token_id)

    @staticmethod
    def create_for_twoFactorAuth(dbConn, *, payload:AuthTokenPayload):
        token = create_access_token(payload.model_dump(),access_token_expire_min=JWTConfig.CHALLENGE_TOKEN_EXPIRE_MINUTES)
        response = TokenRepository.add_to_token_log(dbConn,
                                                    token_id=payload.token_id,
                                                    user_id=payload.user_id,
                                                    email=payload.email,
                                                    token=token,
                                                    purpose=payload.purpose,
                                                    exp_interval_min=JWTConfig.CHALLENGE_TOKEN_EXPIRE_MINUTES
                                                    )
        if not response or response == 0:
            logger.error("Add to token log failed")
            raise ValueError("Add to token log failed")
        return token

    #-----------------NEW SESSION CREATION-------------------
    @staticmethod
    def create_login_session_token(dbConn, *, payload:AuthTokenPayload):
        logger.info(f"Creating Login Session Token...\n PAYLOAD:\n{payload.model_dump()}")
        token = create_access_token(payload.model_dump(),access_token_expire_min=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
        total_rows_affected = TokenRepository.add_to_token_log(dbConn,
                                                    token_id=payload.token_id,
                                                    user_id=payload.user_id,
                                                    email=payload.email,
                                                    token=token,
                                                    purpose=payload.purpose,
                                                    exp_interval_min = JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES
                                                    )
        if not total_rows_affected or total_rows_affected == 0:
            logger.error("Add to token log failed")
            raise ValueError("Add to token log failed")
        return token
    @staticmethod
    def create_refresh_token(dbConn, *, user_id:str, email:str) -> str:
        """Long-lived, single-use token (rotated on every /refresh) that can be
        exchanged for a new LOGIN_SESSION token without re-doing OTP login."""
        payload = AuthTokenPayload(
            token_id=str(uuid4()),
            user_id=user_id,
            email=email,
            purpose=AllowedTokenPurpose.REFRESH_TOKEN
        )
        token = create_access_token(payload.model_dump(), access_token_expire_min=JWTConfig.REFRESH_TOKEN_EXPIRE_MINUTES)
        total_rows_affected = TokenRepository.add_to_token_log(dbConn,
                                                    token_id=payload.token_id,
                                                    user_id=payload.user_id,
                                                    email=payload.email,
                                                    token=token,
                                                    purpose=payload.purpose,
                                                    exp_interval_min=JWTConfig.REFRESH_TOKEN_EXPIRE_MINUTES
                                                    )
        if not total_rows_affected or total_rows_affected == 0:
            logger.error("Add to token log failed")
            raise ValueError("Add to token log failed")
        return token
    #-----------------NEW SESSION CREATION-------------------
    @staticmethod
    def validate_token(dbConn: DBConn, *, token, purpose) -> dict | None:
        decode_data = verify_token(token)
        token_id = decode_data.get('token_id')
        record = TokenRepository.check_valid_token(dbConn=dbConn, token_id=token_id, purpose=purpose)
        if record and record[-1] == decode_data['purpose'] and record[-1] == purpose:
            return decode_data
        raise InvalidTokenError("Token either used or expired!")

    # @staticmethod
    # def validated_set_password_token(dbConn:DBConn,*,token, purpose )->dict | None:
    #     decode_data = verify_token(token)
    #     token_id = decode_data.get('token_id')
    #     record = TokenRepository.check_valid_token(dbConn=dbConn,token_id=token_id,purpose=purpose)
    #     if record and record[-1] ==  decode_data['purpose']:
    #         return decode_data
    #     return None
