import random
from fastapi.exceptions import RequestErrorModel
from jwt import PyJWTError
from core.database import DBConn
from schemas.auth import SignupRequestPayload, SignupResponsePayload, SignUpData, \
    GetCurrentUserRequestPayload, GetCurrentUserResponsePayload, GetCurrentUserData
from schemas.auth import ForgotPasswordRequestPayload, ForgotPasswordResponsePayload
from schemas.auth import SetPasswordRequestPayload, SetPasswordResponsePayload, SetPasswordResponseData
from schemas.auth import LoginRequestPayload,LoginResponsePayload,LoginSessionData,RefreshTokenRequestPayload
from schemas.auth import LoginByEmail,LoginByUserId,LoginByPhone
from schemas.token import AuthTokenPayload
from schemas.otp import OTPBasedTwoFATokenPayload, OTPVerificationRequestPayload
from core.config import AllowedTokenPurpose
from uuid import uuid4
from time import time
from repositories.user_repository import UserRepository
from core.logger import logger
from .mail import EmailServices
from .token import AccessTokenService
from .otp import OTPServices
from fastapi import status
from utils.hashing import hashSecrets,matchSecrets
from fastapi import BackgroundTasks
from exceptions.auth import UserAlreadyExistsException, UnauthorizedException, UserNotFoundException, \
    InternalServerError, PendingUserNotFoundException, PasswordUpdateException
from exceptions.token import InvalidTokenException, ExpiredTokenException
from exceptions.otp import InvalidOTPException, OTPExpiredException

from exceptions.base import AppException

class AuthServices:
    def __init__(self,dbConn:DBConn, backgroundTasks:BackgroundTasks):
        self._dbConn = dbConn
        self._emailServices = EmailServices()
        self._backgroundTask = backgroundTasks
    # Initial Entry point for a new user onboarding.
    def signup(self, *, request:SignupRequestPayload):
        '''
        :param request:
        :return:
        '''
        logger.info("SignUp process start...")
        # Pydantic -> Dict
        request_data = request.model_dump()
        # add UUID
        token_id = request_data['token_id'] = request_data['uuid'] = str(uuid4()) # token id and pending user uuid is same

        # Randomly unique user_id generate
        user_id = request_data['user_id'] =  ( f"{request.first_name[:1].upper()}"
                                    f"{request.last_name[:1].upper()}"
                                    f"{str(int(time() * 1000))[-5:]}"
                                    f"{"".join([random.choice(request.phone) for i in range(3)])}"
                                    )

        # response variable
        logger.info(f"Signup request received :: email={request.email}")
        user_email = request.email
        user_phone = request.phone
        try:
            response = UserRepository.check_user_status(self._dbConn,
                                                        email=user_email,
                                                        phone=user_phone)
            if not response:
                logger.error("query produced no result")
                raise ValueError("query produced no result")

            # check user status ['ACTIVE','NEW_USER', 'PENDING']
            user_status = response[-1]
            logger.info(f'User Status:{user_status}')
            match user_status:
                case 'ACTIVE':
                    raise UserAlreadyExistsException

                case 'PENDING' | 'NEW_USER':
                    total_rows_affected = UserRepository.add_to_pending_user_details(self._dbConn, **request_data)
                    if not total_rows_affected and total_rows_affected == 0:
                        logger.error("Pending user creation FAILED!")
                        raise ValueError("query produced no result")

                    # generate token
                    challenge_token = AccessTokenService.create_for_set_password(dbConn=self._dbConn,
                                                                                 token_id=token_id,
                                                                                 email=user_email,
                                                                                 user_id=user_id,
                                                                                 purpose=AllowedTokenPurpose.SIGN_UP)
                    if not challenge_token:
                        raise ValueError("Token Generation Failed!")
                    self._backgroundTask.add_task(self._emailServices.send_set_password_email, challenge_token=challenge_token, email=user_email)
                case _:
                    raise ValueError("Unknown User Status")

        except AppException as err:
            logger.exception(err.args)
            raise

        except Exception as err:
            logger.exception(err.args)
            raise InternalServerError()
        else:
            self._dbConn.commit()
            return SignupResponsePayload(
                msg="Verification email sent. Please verify your email and set your password.",
                success=True,
                code=status.HTTP_201_CREATED,
                data=SignUpData(
                    email=request.email,
                    email_verification_required=True
                )
            )

    def set_password(self, *, request:SetPasswordRequestPayload, token_payload:dict):
        decode_data = token_payload
        password=request.new_password
        confirm_password = request.confirm_new_password
        if not password or not confirm_password or password != confirm_password:
            logger.error("Password and confirm password not matching")
            raise ValueError("Password not matched")
        # password hashing
        hash_password = hashSecrets(password)
        # Token_id
        token_id = decode_data['token_id']

        user_id = None
        email = None
        try:
            match decode_data['purpose']:
                case AllowedTokenPurpose.SIGN_UP: # SIGN_UP
                    # STEP 1:
                    # fetching pending user data
                    user_data = UserRepository.fetch_pending_user_details(self._dbConn, token_id=token_id)
                    if not user_data or user_data is None:
                        raise PendingUserNotFoundException

                    user_id, email, first_name, last_name, role_type, country_cd, phone = user_data

                    # STEP 2:
                    # Insert into user_details (PASSWORD setting included)
                    total_rows_affected = UserRepository.final_onboarding(self._dbConn,
                                                    uuid=str(uuid4()),
                                                    user_id=user_id,
                                                    email=email,
                                                    first_name=first_name,
                                                    last_name=last_name,
                                                    role_type=role_type,
                                                    country_cd=country_cd,
                                                    phone=phone,
                                                    hash_password=hash_password
                                                   )
                    if not total_rows_affected or  total_rows_affected == 0:
                        logger.error("Final Onboarding data insert failed!")
                        raise InternalServerError

                    rows_affected = AccessTokenService.mark_token_as_used(self._dbConn, token_id=token_id)
                    if not rows_affected or rows_affected == 0:
                        logger.error("Mark token as used updation failed!")
                        raise InternalServerError

                    pending_rows = UserRepository.mark_pending_as_used(self._dbConn, token_id=token_id)
                    if not pending_rows or pending_rows == 0:
                        logger.error("Mark pending registration as used failed!")
                        raise InternalServerError

                    # sending confirmation of account creation.
                    self._backgroundTask.add_task(self._emailServices.account_creation_successful,first_name=first_name,
                                                                    last_name=last_name,
                                                                    email=email,
                                                                    user_id=user_id)

                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # redirect to Login page. (Optional)
                case AllowedTokenPurpose.PASSWORD_RESET:
                    # TODO: FORGET PASSWORD services
                    logger.info("UPCOMING FEATURE ")
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                case _:
                    logger.error("Token Purpose Not allowed!")
                    raise InvalidTokenException

        except AppException as err:
            logger.exception(err.args)
            raise

        except Exception as error:
            logger.exception(error.args)
            raise InternalServerError

        else:
            self._dbConn.commit()
            return SetPasswordResponsePayload(
                msg="Password setup successful",
                code=status.HTTP_201_CREATED,
                success=True,
                data=SetPasswordResponseData(
                user_id=user_id,
                email=email
                )
            )

    #--------------------- LOGIN --------------------------
    def login(self, *, request:LoginRequestPayload, via):
        credential = request.credential
        enteredPassword = request.password

        try:
            # Find out how user try to login
            if isinstance(credential,LoginByPhone):
                logger.info("DETECT: Login By Phone")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_phone(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UserNotFoundException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record

            elif isinstance(credential,LoginByEmail):
                logger.info("DETACT: Login By Email")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_email(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UserNotFoundException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record

            elif isinstance(credential,LoginByUserId):
                logger.info("DETACT: Login By UserId")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_user_id(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UnauthorizedException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record
            else:
                logger.error("Credential not in allowed format")
                raise ValueError("Unknown Credential Format")

            if not is_active:
                logger.error("Inactive user")
                raise UserNotFoundException

            # Password matching
            if not matchSecrets(secret=enteredPassword, hashed_secret=hashed_password):
                logger.error("Password not match.")
                raise UnauthorizedException

            logger.info("✅Password Verification Successful")
            msg = ""
            token = ""
            data = ''
            match is_2fa_enabled:
                case True:

                    if via == 'magic_link':
                        #XXXXXXXXXXXXXXXXXX~~CURRENTLY NOT WORKING~~XXXXXXXXXXXXXXXXXXXXX
                        logger.info("Two Factor Authentication Detected!")
                        # !!!!!!!!!!!!!!!EMAIL_BASED!!!!!!!!!!!!!!!!!
                        twofa_token_payload = AuthTokenPayload(
                            token_id=str(uuid4()),
                            user_id=user_id,
                            email=email,
                            purpose=AllowedTokenPurpose.LOGIN_2FA_MAGIC_URL,
                        )
                        twofa_token = AccessTokenService.create_for_twoFactorAuth(self._dbConn,payload=twofa_token_payload)
                        msg = 'Two Factor Authentication Required! Check Email'
                        if not twofa_token:
                            raise ValueError("Token Generation Failed")

                        BackgroundTasks.add_task(self._emailServices.send_2fa_link,challenge_token=twofa_token,user_id=user_id,first_name=first_name,email=email)
                        # !!!!!!!!!!!!!!!EMAIL_BASED!!!!!!!!!!!!!!!!!
                        # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

                    elif via == 'otp':
                        #!!!!!!!!!!!!!!!!!!OTP BASED!!!!!!!!!!!!!!!!!
                        payload = OTPBasedTwoFATokenPayload(
                            otp_id=str(uuid4()),
                            purpose=AllowedTokenPurpose.LOGIN_2FA_OTP,
                            user_id=user_id,
                            email=email

                        )
                        otp_length = 4
                        OTP, otp_token = OTPServices.create_for_twoFactorAuth(self._dbConn,payload= payload,otp_length=otp_length)
                        if not OTP and not otp_token:
                            logger.error("OTP Generation Failed")
                            raise InternalServerError

                        self._backgroundTask.add_task(self._emailServices.send_2fa_otp,otp=OTP,email=email,purpose=AllowedTokenPurpose.LOGIN_2FA_OTP,exp_at="15 min")
                        token = otp_token
                        msg = "OTP send successful"
                        #!!!!!!!!!!!!!!!!!!OTP BASED!!!!!!!!!!!!!!!!!
                    else:
                        logger.error("TwoFA validation medium not found")
                        raise InternalServerError
                    from schemas.auth import LoginTwoFAData
                    data = LoginTwoFAData(
                        mode=via,
                        challenge_token=token
                    )
                case False:
                # generate token for login
                    session_payload = AuthTokenPayload(
                        token_id=str(uuid4()),
                        user_id=user_id,
                        email=email,
                        purpose=AllowedTokenPurpose.LOGIN_SESSION
                    )
                    # token creation
                    session_token = AccessTokenService.create_login_session_token(self._dbConn,payload=session_payload)
                    if not session_token:
                        raise ValueError("Token Generation Failed!")

                    token = session_token
                    msg = 'Login Successful'
                    from schemas.auth import LoginSessionData
                    data = LoginSessionData(
                        token=token,
                        refresh_token=AccessTokenService.create_refresh_token(self._dbConn, user_id=user_id, email=email)
                    )

        except AppException as error:
            logger.exception(error.args)
            raise

        except Exception as error:
            logger.exception(error.args)
            raise InternalServerError

        else:
            self._dbConn.commit()
            return LoginResponsePayload(
                msg= msg,
                code=status.HTTP_200_OK,
                success=True,
                data= data
            )
    #------------------------------------------------------

    def login_otp_verification(self, *, payload:OTPVerificationRequestPayload):
        PURPOSE = AllowedTokenPurpose.LOGIN_2FA_OTP
        try:
            response_data = OTPServices.verify_otp(self._dbConn, payload=payload, purpose=PURPOSE)
            if not response_data:
                logger.error("Login OTP verification failed!")
                raise InvalidOTPException

            payload = AuthTokenPayload(
                token_id=str(uuid4()),
                user_id= response_data['user_id'],
                email = response_data['email'],
                purpose =  AllowedTokenPurpose.LOGIN_SESSION
            )

            msg = "Login Successful"
            token = AccessTokenService.create_login_session_token(self._dbConn,payload=payload)
            data = LoginSessionData(
                token=token,
                refresh_token=AccessTokenService.create_refresh_token(
                    self._dbConn, user_id=payload.user_id, email=payload.email
                )
            )

        except AppException as err:
            logger.exception(err.args)
            self._dbConn.rollback()
            raise

        except PyJWTError as error:
            logger.exception(error.args)
            self._dbConn.rollback()
            raise OTPExpiredException

        except Exception as err:
            logger.exception(err.args)
            raise InternalServerError

        else:
            self._dbConn.commit()
            return LoginResponsePayload(
                msg=msg,
                success=True,
                code=status.HTTP_200_OK,
                data= data
            )

    def refresh_session(self, *, payload:RefreshTokenRequestPayload):
        """Exchanges a valid refresh token for a new session token + a new
        refresh token. The presented refresh token is marked used, so each one
        works exactly once (rotation)."""
        try:
            try:
                claims = AccessTokenService.validate_token(
                    self._dbConn, token=payload.refresh_token, purpose=AllowedTokenPurpose.REFRESH_TOKEN
                )
            except PyJWTError as error:
                logger.exception(error.args)
                raise InvalidTokenException

            AccessTokenService.mark_token_as_used(self._dbConn, token_id=claims['token_id'])
            session_token = AccessTokenService.create_login_session_token(
                self._dbConn,
                payload=AuthTokenPayload(
                    token_id=str(uuid4()),
                    user_id=claims['user_id'],
                    email=claims['email'],
                    purpose=AllowedTokenPurpose.LOGIN_SESSION
                )
            )
            data = LoginSessionData(
                token=session_token,
                refresh_token=AccessTokenService.create_refresh_token(
                    self._dbConn, user_id=claims['user_id'], email=claims['email']
                )
            )

        except AppException as err:
            logger.exception(err.args)
            self._dbConn.rollback()
            raise

        except Exception as err:
            logger.exception(err.args)
            self._dbConn.rollback()
            raise InternalServerError

        else:
            self._dbConn.commit()
            return LoginResponsePayload(
                msg="Token refreshed",
                success=True,
                code=status.HTTP_200_OK,
                data=data
            )

    def forgot_password(self, *, payload:ForgotPasswordRequestPayload):
        # detact the payload type
        credential = payload.credential
        purpose = AllowedTokenPurpose.PASSWORD_RESET

        try:
            # Find out how user try to login
            if isinstance(credential,LoginByPhone):
                logger.info("DETECT: Login By Phone")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_phone(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UserNotFoundException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record

            elif isinstance(credential,LoginByEmail):
                logger.info("DETACT: Login By Email")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_email(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UserNotFoundException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record

            elif isinstance(credential,LoginByUserId):
                logger.info("DETACT: Login By UserId")
                credential_data = credential.model_dump()
                record = UserRepository.get_user_profile_by_user_id(self._dbConn,**credential_data)
                if not record:
                    logger.error("No active account found")
                    raise UserNotFoundException
                (user_id,email,country_cd,phone,first_name,
                 last_name,full_name,role_type,is_2fa_enabled,
                 is_email_verified,is_phone_verified,hashed_password,is_active) = record
            else:
                logger.error("Credential not in allowed format")
                raise RequestErrorModel

            if not is_active:
                raise UserNotFoundException

            token_id = str(uuid4())
            challenge_token = AccessTokenService.create_for_set_password(self._dbConn, token_id=token_id, purpose=purpose, user_id=user_id, email=email)
            if not challenge_token:
                logger.error("Token Generation Failed!")
                raise InternalServerError
            self._backgroundTask.add_task(self._emailServices.send_reset_password_link,email=email,user_id=user_id,challenge_token = challenge_token)

        except AppException as err:
            self._dbConn.rollback()
            logger.exception(err.args)
            raise
        except Exception as err:
            self._dbConn.rollback()
            logger.exception(err.args)
            raise InternalServerError

        else:
            self._dbConn.commit()
            return ForgotPasswordResponsePayload(data={"email":email})

    def reset_password(self, *, request: SetPasswordRequestPayload, token_payload: dict):
        decode_data = token_payload
        try:
            if request and request.new_password == request.confirm_new_password:
                hashed_password = hashSecrets(request.new_password)
                record = UserRepository.reset_password(self._dbConn,user_id=decode_data['user_id'],
                                                       email=decode_data['email'],
                                                       hashed_password=hashed_password)
                if not record:
                    logger.error("Password updation failed!")
                    raise PasswordUpdateException

                if not AccessTokenService.mark_token_as_used(self._dbConn,token_id=decode_data['token_id']):
                    logger.error("Token update as used Failed!")
                    raise PasswordUpdateException

                self._backgroundTask.add_task(self._emailServices.reset_password_success,
                                              email=decode_data['email'],
                                              user_id = decode_data['user_id'],
                                              change_at = record[0]
                                              )
        except AppException as err:
            self._dbConn.rollback()
            logger.exception(err.args)
            raise

        except Exception as err:
            self._dbConn.rollback()
            logger.exception(err.args)
            raise InternalServerError

        else:
            self._dbConn.commit()
            return SetPasswordResponsePayload(
                msg="Password Updated",
                code=status.HTTP_200_OK,
                success=True,
                data=SetPasswordResponseData(
                    user_id=decode_data['user_id'],
                    email=decode_data['email']
                )
            )

    def get_current_user(self,*,request:GetCurrentUserRequestPayload):
        token = request.token
        purpose = AllowedTokenPurpose.LOGIN_SESSION
        try:
            decode_token = AccessTokenService.validate_token(self._dbConn,token=token,purpose=purpose)
            if not decode_token or decode_token is None:
                raise InvalidTokenException

            user_id = decode_token['user_id']
            record = UserRepository.get_user_profile_by_user_id(self._dbConn,user_id = user_id)
            if not record:
                raise UserNotFoundException
            (user_id, email, country_cd, phone, first_name,
             last_name, full_name, role_type, is_2fa_enabled,
             is_email_verified, is_phone_verified, hashed_password, is_active) = record

            data = GetCurrentUserData(
                user_id=user_id,email=email, first_name=first_name, last_name=last_name, is_active=is_active,
                full_name=full_name,role_type=role_type,phone=phone,country_cd=country_cd, is_2fa_enabled=is_2fa_enabled
            )
        except AppException as err:
            logger.exception(err.args)
            raise
        except PyJWTError as err:
            logger.exception(err.args)
            raise ExpiredTokenException
        except Exception as err:
            logger.exception(err.args)
            raise InternalServerError
        else:
            self._dbConn.commit()
            return GetCurrentUserResponsePayload(
                msg="Authenticated",
                code=status.HTTP_200_OK,
                success=True,
                data = data
            )