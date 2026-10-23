import string
from pydantic_core import PydanticCustomError

def checkValidPasswordPattern(password:str)->str:
    '''

    :param password:
    :return:
    '''
    err_msg = []
    # minimum length 8
    if len(password) < 8:
        err_msg.append("Password must be at least 8 character")

    if ' ' in password:
        err_msg.append("Password should not contained any space")

    # special character contained
    if not any([i in password for i in string.punctuation]):
        err_msg.append(f"Should contained at least one special character {string.punctuation}")
    # digit contained
    if not any([i in password for i in string.digits]):
        err_msg.append(f"Should contained at least one digit{string.digits}")
    # uppercase
    if not any([i in password for i in string.ascii_uppercase]):
        err_msg.append(f"Should contained at least one uppercase letter{string.ascii_uppercase}")
    # lowercase
    if not any([i in password for i in string.ascii_lowercase]):
        err_msg.append(f"Should contained at least one lowercase letter{string.ascii_lowercase}")

    if not err_msg:
        return password

    final_err = "\n".join(err_msg)
    raise PydanticCustomError(
        'password pattern not match',
        '{err_msg}', {'err_msg': final_err}
    )

def checkValidEmailPattern(email:str) -> str:
    '''

    :param email:
    :return:
    '''

    if '@' not in email:
        raise PydanticCustomError(
            'invalid email format', 'An email should contained @'
        )
    return email

def checkPasswordMatch(password:str, confirm_password:str):
    if password != confirm_password:
        raise PydanticCustomError("Password Not Match", "Password and confirm password should match")
    return password


