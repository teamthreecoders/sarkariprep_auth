

from pydantic import BaseModel,Field
from typing import Optional, Any

class ResponseBase(BaseModel):
    msg:str
    success:bool
    code:int
    error:Optional[Any] = None
    data:Any = None

class ErrorDetail(BaseModel):
    issue: str
    details: Optional[Any] = None

class ErrorResponseBase(ResponseBase):
    success:bool = Field(default=False, frozen=True)
    error: Optional[ErrorDetail] = None
    data:Any = Field(default=None, frozen=True)