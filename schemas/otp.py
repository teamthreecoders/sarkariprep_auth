from pydantic import BaseModel, Field
from schemas.base import ResponseBase

class OTPBasedTwoFATokenPayload(BaseModel):
    otp_id:str
    user_id:str
    email:str
    purpose:str

class OTPVerificationRequestPayload(BaseModel):
    challenge_token:str
    otp:str

class OTPVerificationResponseData(BaseModel):
    is_verified:bool
    next_action:str
    purpose:str

class OTPVerificationResponsePayload(ResponseBase):
    data:OTPVerificationResponseData