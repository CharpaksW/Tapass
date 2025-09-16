"""
Email service using SendGrid.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Union, List

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
    
    async def send_wallet_json(self, to_email: str, wallet_data) -> bool:
        """Send wallet JSON as email attachment"""
        if not self.has_sendgrid:
            logger.error("SendGrid not configured")
            return False
        
        try:
            # Check if wallet_data is a list (multiple passes) or single pass
            is_multiple = isinstance(wallet_data, list)
            pass_count = len(wallet_data) if is_multiple else 1
            
            # Convert wallet data to JSON
            json_content = json.dumps(wallet_data, indent=2, ensure_ascii=False)
            json_bytes = json_content.encode('utf-8')
            
            # Create email with appropriate subject and content
            if is_multiple:
                subject = f'Your {pass_count} Wallet Passes JSON'
                content_description = f'Your PDF has been successfully processed and converted to {pass_count} wallet pass JSON files.'
                file_description = f'Please find the wallet.json file attached containing all {pass_count} passes.'
            else:
                subject = 'Your Wallet Pass JSON'
                content_description = 'Your PDF has been successfully processed and converted to a wallet pass JSON format.'
                file_description = 'Please find the wallet.json file attached to this email.'
            
            # Create email
            message = Mail(
                from_email='liorzats.snkr@gmail.com',  # Replace with your verified sender
                to_emails=to_email,
                subject=subject,
                html_content=f"""
                <h2>Your Wallet Pass{' JSON' if not is_multiple else 'es JSON'}</h2>
                <p>Hi there!</p>
                <p>{content_description}</p>
                <p>{file_description}</p>
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
    
    async def send_wallet_pkpass(self, to_email: str, wallet_data: Union[Dict, List[Dict]]) -> bool:
        """Generate and send .pkpass files as email attachments"""
        if not self.has_sendgrid:
            logger.error("SendGrid not configured")
            return False
        
        try:
            # Import PKPassCreator here to avoid circular imports
            from .pdf_to_wallet.pkpasscreator import PKPassCreator
            
            # Check if PKPass generation is configured
            try:
                creator = PKPassCreator()
            except ValueError as e:
                logger.warning(f"PKPass generation not configured: {e}")
                # Fall back to JSON sending
                return await self.send_wallet_json(to_email, wallet_data)
            
            # Check if wallet_data is a list (multiple passes) or single pass
            is_multiple = isinstance(wallet_data, list)
            passes_to_process = wallet_data if is_multiple else [wallet_data]
            pass_count = len(passes_to_process)
            
            attachments = []
            
            # Generate .pkpass files for each pass
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                for i, pass_data in enumerate(passes_to_process):
                    # Create a temporary JSON file for this pass
                    json_filename = f"pass_{i+1}.json" if is_multiple else "pass.json"
                    json_file = temp_path / json_filename
                    
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(pass_data, f, indent=2, ensure_ascii=False)
                    
                    try:
                        # Generate .pkpass file
                        pkpass_path = creator.generate_pkpass(
                            json_file=str(json_file),
                            output_dir=str(temp_path)
                        )
                        
                        # Read the .pkpass file and create attachment
                        with open(pkpass_path, 'rb') as f:
                            pkpass_bytes = f.read()
                        
                        encoded_pkpass = base64.b64encode(pkpass_bytes).decode()
                        filename = Path(pkpass_path).name
                        
                        attachment = Attachment(
                            FileContent(encoded_pkpass),
                            FileName(filename),
                            FileType('application/vnd.apple.pkpass'),
                            Disposition('attachment')
                        )
                        attachments.append(attachment)
                        
                    except Exception as e:
                        logger.error(f"Failed to generate .pkpass file for pass {i+1}: {e}")
                        # Continue with other passes if one fails
                        continue
                
                if not attachments:
                    logger.error("No .pkpass files were generated successfully")
                    # Fall back to JSON sending
                    return await self.send_wallet_json(to_email, wallet_data)
                
                # Create email with appropriate subject and content
                if pass_count > 1:
                    subject = f'Your {pass_count} Apple Wallet Passes'
                    content_description = f'Your PDF has been successfully processed and converted to {len(attachments)} Apple Wallet passes.'
                    file_description = f'Please find the .pkpass files attached. You can open them directly on your iPhone to add them to Apple Wallet.'
                else:
                    subject = 'Your Apple Wallet Pass'
                    content_description = 'Your PDF has been successfully processed and converted to an Apple Wallet pass.'
                    file_description = 'Please find the .pkpass file attached. You can open it directly on your iPhone to add it to Apple Wallet.'
                
                # Create email
                message = Mail(
                    from_email='liorzats.snkr@gmail.com',  # Replace with your verified sender
                    to_emails=to_email,
                    subject=subject,
                    html_content=f"""
                    <h2>Your Apple Wallet Pass{'es' if pass_count > 1 else ''}</h2>
                    <p>Hi there!</p>
                    <p>{content_description}</p>
                    <p>{file_description}</p>
                    <p><strong>How to use:</strong></p>
                    <ul>
                        <li>On iPhone/iPad: Tap the .pkpass file attachment to add it to Apple Wallet</li>
                        <li>On Mac: Double-click the .pkpass file to preview it</li>
                        <li>You can also email the .pkpass file to yourself or others</li>
                    </ul>
                    <br>
                    <p>Best regards,<br>Wallet App Team</p>
                    """
                )
                
                # Add all attachments
                message.attachment = attachments
                
                # Send email
                sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
                response = sg.send(message)
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"Email with {len(attachments)} .pkpass file(s) sent successfully to {to_email}")
                    return True
                else:
                    logger.error(f"SendGrid API error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send .pkpass email: {e}")
            # Fall back to JSON sending
            logger.info("Falling back to JSON email...")
            return await self.send_wallet_json(to_email, wallet_data)
