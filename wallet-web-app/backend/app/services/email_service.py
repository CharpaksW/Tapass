"""
Email service using SendGrid.
"""

import json
import logging
import os
from typing import Dict

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
    import base64
    HAS_SENDGRID = True
except ImportError:
    HAS_SENDGRID = False

logger = logging.getLogger(__name__)


class EmailService:
    """Handles email sending via SendGrid"""
    
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.has_sendgrid = HAS_SENDGRID and self.api_key
        
        if not self.has_sendgrid:
            logger.warning("SendGrid not available or API key not set")
    
    async def send_wallet_json(self, to_email: str, wallet_data: Dict) -> bool:
        """Send wallet JSON as email attachment"""
        if not self.has_sendgrid:
            logger.error("SendGrid not configured")
            return False
        
        try:
            # Convert wallet data to JSON
            json_content = json.dumps(wallet_data, indent=2, ensure_ascii=False)
            json_bytes = json_content.encode('utf-8')
            
            # Create email
            message = Mail(
                from_email='noreply@walletapp.com',  # Replace with your verified sender
                to_emails=to_email,
                subject='Your Wallet JSON',
                html_content=f"""
                <h2>Your Wallet Pass JSON</h2>
                <p>Hi there!</p>
                <p>Your PDF has been successfully processed and converted to a wallet pass JSON format.</p>
                <p>Please find the wallet.json file attached to this email.</p>
                <p>You can use this JSON file to create Apple Wallet passes or integrate with other wallet services.</p>
                <br>
                <p>Best regards,<br>Wallet App Team</p>
                """
            )
            
            # Create attachment
            encoded_json = base64.b64encode(json_bytes).decode()
            attachment = Attachment(
                FileContent(encoded_json),
                FileName('wallet.json'),
                FileType('application/json'),
                Disposition('attachment')
            )
            message.attachment = attachment
            
            # Send email
            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"SendGrid API error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
