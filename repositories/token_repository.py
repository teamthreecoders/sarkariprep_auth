from CRUD.token import add_to_token_log, mark_as_used, check_valid_token_for_onboarded_user, \
    check_valid_token_for_non_onboarded_user
from core.config import AllowedTokenPurpose
from core.database import DBConn
from core.logger import  logger

class TokenRepository:

    @staticmethod
    def add_to_token_log(dbConn:DBConn,*, token_id:str,user_id:str,email:str,token:str,purpose:str, exp_interval_min:int)-> None | int:
        variables = (token_id,user_id,email,token,purpose)
        query = add_to_token_log(exp_interval_min)
        logger.info(f"VARIABLES::{variables}")
        total_rows_affected = dbConn.execute_command(query=query,variables=variables)
        return total_rows_affected

    @staticmethod
    def check_valid_token(dbConn:DBConn,*, token_id, purpose):
        variables = (token_id,purpose,)
        query = check_valid_token_for_non_onboarded_user if purpose == AllowedTokenPurpose.SIGN_UP else check_valid_token_for_onboarded_user
        logger.info(f"VARIABLES::{variables}")
        record = dbConn.execute_query(query=query,variables=variables, fetchone=True)
        return record

    @staticmethod
    def update_token_log(dbConn:DBConn,*,token_id:str):
        variables = (token_id,)
        query = mark_as_used
        logger.info(f"VARIABLES::{variables}")
        total_rows_affected = dbConn.execute_command(query=query,variables=variables)
        return total_rows_affected