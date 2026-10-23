from smtplib import SMTP
from smtplib import SMTPResponseException
from core.config import SMTPConfig
from core.logger import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_smtp_connection():
    """
    Establishes a connection to the SMTP server using the configuration provided in SMTPConfig.
    It attempts to connect to the SMTP server, start TLS encryption, and log in using the provided email and password.
    If successful, it returns the SMTP server object. If any step fails, it logs the error and raises the exception.

    Returns:
        SMTP: An instance of the SMTP class representing the connection to the SMTP server.
    Raises:
        Exception: If there is an error during the connection, TLS setup, or login process,
                     the exception is logged and re-raised for further handling.

    """
    try:
        logger.info(f"⟪{SMTPConfig.HOST}⟫\n◉ SMTP SERVER Connecting...")
        server = SMTP(
            host=SMTPConfig.HOST,
            port=SMTPConfig.PORT,
            timeout= SMTPConfig.TIMEOUT
        )
        logger.info(f"✅ Connected!")

        server.starttls()
        logger.info(f"⏳LogIn to {SMTPConfig.EMAIL}")
        server.login(
            SMTPConfig.EMAIL,
            SMTPConfig.PASSWORD
        )
        logger.info(f"✅ Login successful!")
        return server
    
    except Exception as error:
        logger.error(f"❌ SMTP SERVER Connection Failed!\nCAUSE::{error}")
        raise error

        