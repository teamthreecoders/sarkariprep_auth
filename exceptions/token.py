from .base import AppException

class InvalidTokenException(AppException):

    def __init__(self):
        super().__init__(msg="Invalid token", status_code=401, error="Unauthorized")


class ExpiredTokenException(AppException):

    def __init__(self):
        super().__init__(msg="Token expired", status_code=401, error="Unauthorized")

