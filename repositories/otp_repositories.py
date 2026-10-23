from CRUD.otp import add_to_otp_log, check_valid_otp, mark_as_used
from core.database import DBConn
from core.logger import  logger

class OTPRepository:
    @staticmethod
    def add_to_otp_log(dbConn:DBConn, *, otp_id:str,email:str,user_id:str,hashed_otp:str,purpose:str):
        variables = (otp_id, email, user_id, hashed_otp, purpose)
        query = add_to_otp_log
        logger.info(f"VARIABLES::{variables}")
        rows_affected = dbConn.execute_command(query= query, variables=variables)
        return rows_affected

    @staticmethod
    def check_valid_otp(dbConn:DBConn, *,email:str,user_id:str,otp_id:str,purpose:str):
        variables = (email,user_id,otp_id,purpose)
        query = check_valid_otp
        logger.info(f"VARIABLES::{variables}")
        record = dbConn.execute_query(query= query, variables=variables,fetchone=True)
        return record

    @staticmethod
    def mark_as_used(dbConn:DBConn,*, otp_id:str, user_id:str):
        variables = (otp_id,user_id,)
        query = mark_as_used
        logger.info(f"VARIABLES::{variables}")
        rows_affected = dbConn.execute_command(query= query, variables=variables)
        return rows_affected

