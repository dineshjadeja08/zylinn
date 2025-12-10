"""
Email Service
Handles email sending via SendGrid for verification and password reset.
"""
import os
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import structlog

logger = structlog.get_logger(__name__)

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@zylin.ai")
FROM_NAME = os.getenv("FROM_NAME", "Zylin AI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.zylin.ai")


class EmailService:
    """Email service using SendGrid"""
    
    def __init__(self):
        self.api_key = SENDGRID_API_KEY
        self.from_email = FROM_EMAIL
        self.from_name = FROM_NAME
        self.frontend_url = FRONTEND_URL
        
        if not self.api_key:
            logger.warning("sendgrid_api_key_not_configured")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SendGrid.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text fallback (optional)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.api_key:
            logger.error("sendgrid_not_configured", to=to_email)
            return False
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            if text_content:
                message.plain_text_content = Content("text/plain", text_content)
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            logger.info(
                "email_sent",
                to=to_email,
                subject=subject,
                status_code=response.status_code
            )
            
            return response.status_code in (200, 201, 202)
        
        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to_email,
                error=str(e)
            )
            return False
    
    def send_verification_email(self, to_email: str, full_name: str, verification_token: str) -> bool:
        """
        Send email verification link.
        
        Args:
            to_email: User's email address
            full_name: User's full name
            verification_token: Verification token
        
        Returns:
            True if sent successfully
        """
        verification_url = f"{self.frontend_url}/verify-email?token={verification_token}"
        
        subject = "Verify your Zylin account"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #777; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Zylin! 🎉</h1>
                </div>
                <div class="content">
                    <p>Hi {full_name or 'there'},</p>
                    
                    <p>Thanks for signing up for Zylin AI Voice Agent! We're excited to have you on board.</p>
                    
                    <p>To get started, please verify your email address by clicking the button below:</p>
                    
                    <center>
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </center>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="background: #fff; padding: 10px; border-radius: 4px; word-break: break-all;">
                        {verification_url}
                    </p>
                    
                    <p><strong>This link will expire in 24 hours.</strong></p>
                    
                    <p>If you didn't create a Zylin account, you can safely ignore this email.</p>
                    
                    <p>Best regards,<br>The Zylin Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 Zylin AI. All rights reserved.</p>
                    <p>If you have any questions, contact us at support@zylin.ai</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Zylin!
        
        Hi {full_name or 'there'},
        
        Thanks for signing up for Zylin AI Voice Agent!
        
        Please verify your email address by visiting this link:
        {verification_url}
        
        This link will expire in 24 hours.
        
        If you didn't create a Zylin account, you can safely ignore this email.
        
        Best regards,
        The Zylin Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_password_reset_email(self, to_email: str, full_name: str, reset_token: str) -> bool:
        """
        Send password reset link.
        
        Args:
            to_email: User's email address
            full_name: User's full name
            reset_token: Password reset token
        
        Returns:
            True if sent successfully
        """
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset your Zylin password"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #777; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hi {full_name or 'there'},</p>
                    
                    <p>We received a request to reset your Zylin account password.</p>
                    
                    <p>Click the button below to set a new password:</p>
                    
                    <center>
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </center>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="background: #fff; padding: 10px; border-radius: 4px; word-break: break-all;">
                        {reset_url}
                    </p>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong>
                        <ul>
                            <li>This link will expire in 1 hour</li>
                            <li>If you didn't request a password reset, please ignore this email</li>
                            <li>Never share this link with anyone</li>
                        </ul>
                    </div>
                    
                    <p>Best regards,<br>The Zylin Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 Zylin AI. All rights reserved.</p>
                    <p>If you have any questions, contact us at support@zylin.ai</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        Hi {full_name or 'there'},
        
        We received a request to reset your Zylin account password.
        
        Visit this link to set a new password:
        {reset_url}
        
        ⚠️ Security Notice:
        - This link will expire in 1 hour
        - If you didn't request a password reset, please ignore this email
        - Never share this link with anyone
        
        Best regards,
        The Zylin Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_welcome_email(self, to_email: str, full_name: str, api_key: str) -> bool:
        """
        Send welcome email with API key after verification.
        
        Args:
            to_email: User's email address
            full_name: User's full name
            api_key: Generated API key
        
        Returns:
            True if sent successfully
        """
        subject = "Welcome to Zylin - Your API Key"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .api-key {{ background: #fff; padding: 15px; border-radius: 4px; font-family: monospace; word-break: break-all; border: 2px solid #667eea; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #777; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>You're All Set! 🚀</h1>
                </div>
                <div class="content">
                    <p>Hi {full_name or 'there'},</p>
                    
                    <p>Your email has been verified! Here's your API key to get started with Zylin:</p>
                    
                    <div class="api-key">
                        <strong>API Key:</strong><br>
                        {api_key}
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Important:</strong>
                        <ul>
                            <li>Keep this API key secret</li>
                            <li>Never commit it to version control</li>
                            <li>Use environment variables in production</li>
                            <li>You can regenerate it anytime from your dashboard</li>
                        </ul>
                    </div>
                    
                    <h3>Quick Start</h3>
                    <p>Make your first API call:</p>
                    <pre style="background: #fff; padding: 15px; border-radius: 4px; overflow-x: auto;">
curl -H "X-API-Key: {api_key}" \\
  https://api.zylin.ai/calls</pre>
                    
                    <center>
                        <a href="{self.frontend_url}/dashboard" class="button">Go to Dashboard</a>
                        <a href="{self.frontend_url}/docs" class="button" style="background: #764ba2;">View API Docs</a>
                    </center>
                    
                    <p>Need help? Check out our <a href="{self.frontend_url}/docs">documentation</a> or contact support@zylin.ai</p>
                    
                    <p>Best regards,<br>The Zylin Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 Zylin AI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        You're All Set!
        
        Hi {full_name or 'there'},
        
        Your email has been verified! Here's your API key:
        
        {api_key}
        
        ⚠️ Important:
        - Keep this API key secret
        - Never commit it to version control
        - Use environment variables in production
        
        Quick Start:
        curl -H "X-API-Key: {api_key}" https://api.zylin.ai/calls
        
        Dashboard: {self.frontend_url}/dashboard
        API Docs: {self.frontend_url}/docs
        
        Best regards,
        The Zylin Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
