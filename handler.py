from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from exceptions.base import AppException
from schemas.base import ErrorResponseBase, ErrorDetail


async def pydantic_exception_handler(
        request:Request,
        exception:RequestValidationError
):
    from core.logger import logger
    logger.error(exception.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponseBase(
            msg="Request payload error",
            code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error=ErrorDetail(
                issue="Validation Failed",
                details=exception.errors(),
            ),
        ).model_dump()
    )


async def app_exception_handler(
        request:Request,
        exception:AppException
):
    return JSONResponse(
        status_code=exception.status_code,
        content=ErrorResponseBase(
            msg=exception.msg,
            code=exception.status_code,
            error=ErrorDetail(
                issue=exception.error,
                details=None,
            ),
        ).model_dump()
    )

