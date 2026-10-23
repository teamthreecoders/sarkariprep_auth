# It is AI generated code. Understanble
import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "/tmp/logs" if not os.access(".", os.W_OK) else "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Log format
LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | "
    "%(name)s | %(filename)s:%(lineno)d | %(message)s"
)

# Configure logger
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT
)

# File handler
file_handler = RotatingFileHandler(
    f"{LOG_DIR}/app.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5
)

file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Root logger
logger = logging.getLogger("fastapi-app")

# Avoid duplicate handlers
if not logger.handlers:
    logger.addHandler(file_handler)

logger.setLevel(logging.INFO)