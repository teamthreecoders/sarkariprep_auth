from pydantic import BaseModel, Field, EmailStr, field_validator, AfterValidator,BeforeValidator
from typing import Optional, Literal, Any, List, Dict, Union, Annotated
from schemas.base import ResponseBase
from schemas.validator import *

class GetCurrentUserRequestPayload(BaseModel):
    token:str
class GetCurrentUserData(BaseModel):
    user_id:str
    first_name:str
    last_name:str
    full_name:str
    is_active:bool
    role_type:str
    email:str
    phone:str
    country_cd:str
    is_2fa_enabled:bool

class GetCurrentUserResponsePayload(ResponseBase):
    data:GetCurrentUserData

class SignupRequestPayload(BaseModel):
    first_name:Annotated[str,Field(description="User first name", min_length= 3)]
    last_name: Annotated[str,Field(description="User last name", min_length= 3)]
    role_type: Optional[Literal[
        'user',
        'admin',
        'guest',
        'other'
    ]] = Field(
        default='user',
        description="User role"
    )
    email: Annotated[str, Field(description="User email ID"), AfterValidator(checkValidEmailPattern)]
    country_cd: str = Field(
        default='+91',
        description="Country code",
        pattern=r"^\+\d{2}$"
    )
    phone: str = Field(
        description="10 digit phone number",
        pattern=r"^\d{10}$", min_length=10, max_length=10
    )

class SignUpData(BaseModel):
    email: str
    email_verification_required: bool = True

class SignupResponsePayload(ResponseBase):
    data:Union[SignUpData,None]

#--------------LOGIN-------------
# ------------REQUEST------------
class LoginByEmail(BaseModel):
    email:Annotated[str,AfterValidator(checkValidEmailPattern)]

class LoginByPhone(BaseModel):
    country_cd:str
    phone:str

class LoginByUserId(BaseModel):
    user_id:str

class LoginRequestPayload(BaseModel):
    credential:Union[LoginByEmail,LoginByUserId,LoginByPhone]
    password: Annotated[str, AfterValidator(checkValidPasswordPattern)]
# ------------REQUEST--------------

#~~~~~~~~~~~~~RESPONSE~~~~~~~~~~
class LoginSessionData(BaseModel):
    token:str
    refresh_token:Optional[str] = None

class LoginTwoFAData(BaseModel):
    mode:str
    challenge_token:str

class LoginResponsePayload(ResponseBase):
    data:Union[LoginSessionData,LoginTwoFAData,None]
# ~~~~~~~~~~~~~RESPONSE~~~~~~~~~~
#----------------------------------


class SetPasswordRequestPayload(BaseModel):
    new_password:Annotated[str, AfterValidator(checkValidPasswordPattern)]
    confirm_new_password:str

class SetPasswordResponseData(BaseModel):
    user_id:str
    email:str

class SetPasswordResponsePayload(ResponseBase):
    data:SetPasswordResponseData

class ForgotPasswordRequestPayload(BaseModel):
    credential:Union[LoginByEmail,LoginByUserId,LoginByPhone]

class ForgotPasswordResponsePayload(ResponseBase):
    msg:str = "If an account exists for this email, a password reset link has been sent."
    success:bool = True
    code:int = 202
class RefreshTokenRequestPayload(BaseModel):
    refresh_token:str

class LogOutResponsePayload(ResponseBase):
    msg:str = "Log Out successful"
    success:bool = True
    code:int = 202