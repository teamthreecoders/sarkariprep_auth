
from core.config import JWTConfig
from core.database import DBConn
from repositories.otp_repositories import OTPRepository
from schemas.otp import OTPBasedTwoFATokenPayload, OTPVerificationRequestPayload
import secrets, string
from core.security import create_access_token, verify_token
from utils.hashing import hashSecrets, matchSecrets
from core.logger import logger

class OTPServices:
    '''
    All the otp based services will be done over here.
    1. Two factor Authentication

    '''
    @staticmethod
    def __generate_otp(length:int):
        return "".join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def create_for_twoFactorAuth(dbConn:DBConn, *, payload:OTPBasedTwoFATokenPayload, otp_length:int = 4)-> tuple[str,str]:
        OTP = OTPServices.__generate_otp(length=otp_length)
        token = create_access_token(payload.model_dump(), access_token_expire_min=JWTConfig.OTP_EXPIRE_MINUTES)
        hashed_otp = hashSecrets(OTP)
        response = OTPRepository.add_to_otp_log(dbConn=dbConn, otp_id=payload.otp_id, email=payload.email,
                                                user_id=payload.user_id, hashed_otp=hashed_otp, purpose=payload.purpose)
        if not response:
            logger.error("Unable to insert data")
            raise ValueError("OTP Creation failed")
        return OTP,token

    @staticmethod
    def verify_otp(dbConn:DBConn, *, payload:OTPVerificationRequestPayload, purpose:str):
        from exceptions.otp import InvalidOTPException,OTPExpiredException
        decode_data = verify_token(payload.challenge_token)
        if decode_data['purpose'] != purpose:
            logger.error("Invalid Purpose")
            raise InvalidOTPException
        # logger.info(f"Decoded data{decode_data}")
        decode_data.pop('exp')
        record = OTPRepository.check_valid_otp(dbConn,**decode_data)
        if not record :
            logger.error("OTP not found in DB log.")
            raise OTPExpiredException

        if record[-1] != purpose or not matchSecrets(secret=payload.otp, hashed_secret=record[0]):
            logger.error("OTP not matched")
            raise InvalidOTPException
        response = OTPRepository.mark_as_used(dbConn,otp_id=decode_data['otp_id'], user_id=decode_data['user_id'])
        if not response:
            logger.error("OTP Verification failed")
            raise ValueError("OTP Verification failed")
        return decode_data