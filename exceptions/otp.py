from .base import AppException


class InvalidOTPException(AppException):
    def __init__(self):
        super().__init__(
            msg="Invalid OTP",
            status_code=401,
            error="Unauthorized"
        )

class OTPExpiredException(AppException):
    def __init__(self):
        super().__init__(
            msg="OTP expired",
            status_code=401,
            error="Unauthorized"
        )


