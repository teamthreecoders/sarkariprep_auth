class AppException(Exception):
    def __init__(self, *, msg:str,status_code:int = 400, error:str = "Application Error"):
        self.msg = msg
        self.status_code = status_code
        self.error = error
        super().__init__(msg)

