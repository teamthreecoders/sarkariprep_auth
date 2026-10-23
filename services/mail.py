from typing import Literal

from core.SMTP import get_smtp_connection
from jinja2 import Environment, FileSystemLoader
from core.config import EMAIL_VERIFICATION_BASEURL, SMTPConfig
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.logger import logger
class EmailServices:
    _env = Environment(loader=FileSystemLoader("templates/email"))

    def __init__(self):
        self._conn = get_smtp_connection()

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    def __send_email(self, *, sub, to, cc=None, bcc=None, body, body_type):
        # Use "alternative" if you are sending HTML with a text fallback
        # Use "mixed" if you plan to add attachments later
        msg = MIMEMultipart("alternative")
        msg['Subject'] = sub
        msg['From'] = SMTPConfig.EMAIL

        # 1. Properly format recipients if they are passed as lists
        msg['To'] = ", ".join(to) if isinstance(to, list) else to
        if cc:
            msg['Cc'] = ", ".join(cc) if isinstance(cc, list) else cc
        if bcc:
            msg['Bcc'] = ", ".join(bcc) if isinstance(bcc, list) else bcc

        # 2. Attach the body to the multipart container
        mime_body = MIMEText(body, body_type, 'utf-8')
        msg.attach(mime_body)

        # 3. FIX: Send the entire message container, not just the body fragment
        self._conn.send_message(msg)
        logger.info("Email Send successful.")

    def send_set_password_email(self,*,challenge_token:str,email:str):
        url = EMAIL_VERIFICATION_BASEURL+f"/set-password?challenge_token={challenge_token}"
        template = self._env.get_template("set_password_email.html")

        body = template.render(set_password_link=url)


        subject = "Action Required! Set password"
        self.__send_email(sub=subject, to=email, body=body, body_type='html')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


    def send_2fa_otp(self,*,otp:str,email:str,exp_at:str,purpose):
        # OTP_CONFIG = {
        #     "login": {"subject": "Your Login OTP", "template": "otp_login.html"},
        #     "signup": {"subject": "Verify your Email", "template": "otp_signup.html"},
        #     "forgot_password": {"subject": "Password Reset OTP", "template": "otp_forgot_password.html"},
        #     "sensitive_action": {"subject": "Action Verification OTP", "template": "otp_sensitive_action.html"},
        # }
        template = self._env.get_template("otp_2fa.html")
        subject = f"Your SarkariPrep login code: {otp}"
        html = template.render(
            app_name="SarkariPrep",
            user_email=email,
            otp=list(otp),  # ["4","8","3","9","1","2"]
            expires_in="10 minutes",
        )
        self.__send_email(sub=subject, to=email,body=html, body_type='html')

    def account_creation_successful(self,*,first_name:str,last_name:str, email,user_id):
        fullname = first_name.title().strip()+" "+last_name.title().strip()
        templates = self._env.get_template("successful_account_creation.html")
        subject = "Welcome to SarkariPrep — You're all set! 🎉"
        body = templates.render(full_name = fullname,user_email=email, user_id=user_id)
        self.__send_email(sub=subject,to=email, body=body,body_type='html')


    def send_2fa_link(self,*,challenge_token:str, user_id:str,email:str, first_name:str):
        template = self._env.get_template("TwoFA_base.html")
        body = template.render(
            app_name="SarkariPrep",
            first_name=first_name,
            user_email=email,
            auth_link=f"{EMAIL_VERIFICATION_BASEURL}/2fa/confirm?challenge_token={challenge_token}",
            expires_in="15 minutes",
            request_location="Chennai, IN",
        )
        subject = "Action required: Confirm your SarkariPrep login"
        self.__send_email(sub=subject,to=email, body=body,body_type='html')


    def send_reset_password_link(self,*,email:str,user_id:str,challenge_token:str):
        url = EMAIL_VERIFICATION_BASEURL+f"/reset-password?challenge_token={challenge_token}"
        template = self._env.get_template("reset_password.html")

        body = template.render(    app_name="SarkariPrep",
                                user_email=email,
                                reset_link=url,
                                expires_in="15 minutes",
                               )
        subject = "Reset your SarkariPrep password"
        self.__send_email(sub=subject, to=email, body=body, body_type='html')

    def reset_password_success(self,*,email:str,user_id:str,change_at:str):
        template = self._env.get_template("password_reset_success.html")

        body = template.render(
            app_name="SarkariPrep",
            user_email=email,
            user_id=user_id,
            changed_at=change_at,
            support_url="https://support.myapp.com",
        )
        subject = "Your SarkariPrep password has been reset"
        self.__send_email(sub=subject, to=email, body=body, body_type='html')





