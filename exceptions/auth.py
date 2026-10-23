from .base import AppException
from fastapi import status

class UserAlreadyExistsException(AppException):
    def __init__(self):
        msg = "User EmailId or PhoneNo already registered."
        error_code = 409
        error = "Conflict"
        super().__init__(msg=msg, status_code=error_code, error=error)

class UserNotFoundException(AppException):
    def __init__(self):
        super().__init__(msg="User Not Found", status_code=status.HTTP_404_NOT_FOUND, error="Not Found")

class UnauthorizedException(AppException):
    def __init__(self):
        super().__init__(msg="Invalid login credential", status_code=status.HTTP_401_UNAUTHORIZED,
                         error="Unauthorized")

class InternalServerError(AppException):
    def __init__(self):
        super().__init__(msg="Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                         error="Internal Sever Error")

class PasswordMismatchException(AppException):
    def __init__(self):
        super().__init__(msg="Password & Confirm Password Not Match", status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                         error="Password Mismatch")

class PendingUserNotFoundException(AppException):
    msg = "Pending user not found"
    status_code = status.HTTP_404_NOT_FOUND
    error = "Not Found"

class PasswordUpdateException(AppException):
    msg = "Password reset failed!"
    status_code = status.HTTP_400_BAD_REQUEST
    error = "Password reset failed"



