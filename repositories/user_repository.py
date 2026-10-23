from CRUD.auth import (add_to_pending_user_details, setup_new_password, check_user_status, final_onboarding,
                       fetch_pending_user_details,
                       get_user_profile_by_user_id, get_user_profile_by_email, get_user_profile_by_phone,
                       reset_password, mark_pending_as_used)
from core.database import DBConn
from core.logger import  logger

class UserRepository:
    # ------------------------SIGN UP------------------------
    @staticmethod
    def check_user_status(dbConn:DBConn,*,email:str,phone:str):
        variables = (phone,email,email,email,)
        query = check_user_status
        logger.info(f"VARIABLES::",{variables})
        records = dbConn.execute_query(query=query,variables=variables, fetchone=True)
        logger.info("Records:\n{}".format(records))
        # return only 1 row {}
        return records

    @staticmethod
    def add_to_pending_user_details(dbConn:DBConn , * , uuid:str,user_id:str,first_name:str ,last_name:str ,role_type:str ,email:str, phone:str, country_cd:str, token_id:str):
        variables = (uuid,user_id,first_name,last_name,role_type,email,country_cd,phone,token_id)
        query = add_to_pending_user_details
        logger.info(f"VARIABLES::{variables}")
        rows_affected = dbConn.execute_command(query=query, variables=variables)
        return rows_affected

    @staticmethod
    def fetch_pending_user_details(dbConn: DBConn, *, token_id: str):
        variables = (token_id,)
        query = fetch_pending_user_details
        logger.info(f"VARIABLES::{variables}")
        records = dbConn.execute_query(query=query, variables=variables, fetchone=True)
        return records

    @staticmethod
    def final_onboarding(dbConn:DBConn,*, uuid:str,user_id:str,first_name:str ,last_name:str ,role_type:str ,email:str, phone:str, country_cd:str,hash_password:str):
        variables =(uuid,
        user_id,
        email,
        first_name,
        last_name,
        role_type,
        country_cd,
        phone)

        query = final_onboarding
        logger.info(f"VARIABLES::{variables}")
        rows_affected = dbConn.execute_command(query=query, variables=variables)
        if rows_affected  > 0:
            logger.info("Add to user details")
            # new password setup
            query = setup_new_password
            variables = (uuid,user_id,hash_password,'True','True')
            rows_affected = dbConn.execute_command(query=query, variables=variables)
        else:
            raise ValueError("User Onboarding Failed")
        return rows_affected

    # ---------------------------------------------------

    # ----------------- FETCH USER PROFILE----------------------
    # By user_id
    @staticmethod
    def get_user_profile_by_user_id(dbConn: DBConn, *, user_id: str):
        variables = (user_id,)
        query = get_user_profile_by_user_id
        logger.info(f"VARIABLES::{variables}")
        records = dbConn.execute_query(query=query, variables=variables, fetchone=True)
        return records

    # By email
    @staticmethod
    def get_user_profile_by_email(dbConn: DBConn, *, email: str):
        variables = (email,)
        query = get_user_profile_by_email
        logger.info(f"VARIABLES::{variables}")
        records = dbConn.execute_query(query=query, variables=variables, fetchone=True)
        return records

    # By phone
    @staticmethod
    def get_user_profile_by_phone(dbConn: DBConn, *, country_cd: str, phone: str) -> tuple | None:
        variables = (country_cd, phone,)
        query = get_user_profile_by_phone
        logger.info(f"VARIABLES::{variables}")
        records = dbConn.execute_query(query=query, variables=variables, fetchone=True)
        return records

    # --------------------FETCH USER PROFILE-------------------

    # UPDATE PASSWORD / PASSWORD CHANGE
    @staticmethod
    def mark_pending_as_used(dbConn: DBConn, *, token_id: str):
        variables = (token_id,)
        query = mark_pending_as_used
        logger.info(f"VARIABLES::{variables}")
        rows_affected = dbConn.execute_command(query=query, variables=variables)
        return rows_affected

    @staticmethod
    def reset_password(dbConn:DBConn,*,user_id:str,email:str, hashed_password:str):
        variables = (hashed_password, user_id,email,)
        query = reset_password
        logger.info(f"VARIABLES::{variables}")
        records = dbConn.execute_query(query=query, variables=variables, fetchone=True)
        return records




