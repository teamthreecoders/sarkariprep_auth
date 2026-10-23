from datetime import datetime, UTC

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.v1.auth import route as auth_route
from routes.webpage.webpage import router as page_route
from handler import *
from core.config import CORS_ALLOWED_ORIGINS

app = FastAPI(title="Authentication")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ``````````````EXCEPTION HANDLER````````````````
# Request payload data error or structure error
app.add_exception_handler(
    RequestValidationError,
    pydantic_exception_handler
)

app.add_exception_handler(
    AppException,
    app_exception_handler
)
# ```````````````````````````````````````````````



@app.api_route("/", status_code=status.HTTP_200_OK,methods=['POST','GET'])
def home():
    return {
        'msg':"Hello, I am good! How are you?🐼🐼"
    }

@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {
        "status": "UP",
        "service": "auth-service",
        "timestamp": datetime.now(UTC).isoformat()
    }

app.include_router(auth_route)
app.include_router(page_route)

