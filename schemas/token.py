from pydantic import BaseModel, Field
from core.config import AllowedTokenPurpose

class AuthTokenPayload(BaseModel):
    token_id:str
    purpose:AllowedTokenPurpose | str
    email:str
    user_id:str

class ChallengeTokenPayload(BaseModel):
    token_id:str
    purpose:AllowedTokenPurpose | str
    email:str
    user_id:str