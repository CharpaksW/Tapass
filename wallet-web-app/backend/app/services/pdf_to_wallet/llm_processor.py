"""
LLM Processor for full PDF content analysis using Vision API.

This processor sends the PDF as images to OpenAI's Vision API with a structured prompt
and expects a JSON response containing extracted wallet pass data.
"""

import base64
import json
import logging
import os
from typing import Dict, Optional, Any, List
from io import BytesIO

from .llm_prompt import get_vision_extraction_prompt
from .category_processors import process_llm_data_to_wallet_passes

logger = logging.getLogger(__name__)

# Try to import required libraries
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI library not available. Install with: pip install openai")

try:
    import fitz  # PyMuPDF
    from PIL import Image
    HAS_PDF_LIBS = True
except ImportError:
    HAS_PDF_LIBS = False
    logger.warning("PDF processing libraries not available. Install with: pip install pymupdf pillow")


class LLMProcessor:
    """Processes entire PDF content using LLM for structured data extraction"""
    
    def __init__(self, api_key_env: str = "OPENAI_API_KEY"):
        """
        Initialize LLM processor.
        
        Args:
            api_key_env: Environment variable name containing OpenAI API key
        """
        self.api_key = os.getenv(api_key_env)
        self.has_openai = HAS_OPENAI and self.api_key
        self.has_pdf_libs = HAS_PDF_LIBS
        
        if not self.has_openai:
            logger.warning("LLM processor not available - missing OpenAI library or API key")
        if not self.has_pdf_libs:
            logger.warning("PDF processing libraries not available - cannot convert PDF to images")
    
    def pdf_to_images(self, pdf_path: str, max_pages: int = 3) -> List[str]:
        """
        Convert PDF pages to base64 encoded images.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum number of pages to convert (to avoid token limits)
            
        Returns:
            List of base64 encoded image strings
        """
        if not self.has_pdf_libs:
            logger.error("Cannot convert PDF to images - missing PDF processing libraries")
            return []
        
        try:
            images = []
            doc = fitz.open(pdf_path)
            
            # Limit pages to avoid token limits
            num_pages = min(len(doc), max_pages)
            logger.info(f"Converting {num_pages} pages from PDF to images")
            
            for page_num in range(num_pages):
                page = doc[page_num]
                
                # Render page to image with good quality
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to base64
                base64_image = base64.b64encode(img_data).decode('utf-8')
                images.append(base64_image)
                
                logger.info(f"Converted page {page_num + 1} to base64 image ({len(base64_image)} chars)")
            
            doc.close()
            return images
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            return []
    
    def build_vision_prompt(self, timezone: str = "+00:00", fallback_locale: str = "en-US") -> str:
        """
        Build the prompt for vision-based LLM processing.
        
        Args:
            timezone: Timezone offset (e.g., "+03:00")
            fallback_locale: Fallback locale (e.g., "he-IL" or "en-US")
            
        Returns:
            Formatted prompt string for vision processing
        """
        return get_vision_extraction_prompt(timezone=timezone, fallback_locale=fallback_locale)
    
    async def process_pdf_with_vision(self, pdf_path: str, organization: str, 
                                     pass_type_id: str, team_id: str, 
                                     timezone: str = "+00:00", fallback_locale: str = "en-US",
                                     model: str = "gpt-4o") -> Optional[Dict[str, Any]]:
        """
        Process PDF using Vision API to extract structured wallet pass data.
        
        Args:
            pdf_path: Path to PDF file
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier
            team_id: Apple Developer team ID
            timezone: Timezone offset (e.g., "+03:00")
            fallback_locale: Fallback locale (e.g., "he-IL" or "en-US")
            model: OpenAI model to use (must support vision)
            
        Returns:
            Dictionary containing extracted data structure or None if failed
        """
        if not self.has_openai:
            logger.error("LLM processor not available - missing OpenAI library or API key")
            return None
        
        if not self.has_pdf_libs:
            logger.error("Cannot process PDF - missing PDF processing libraries")
            return None
        
        try:
            # Convert PDF to images
            images = self.pdf_to_images(pdf_path)
            if not images:
                logger.error("Failed to convert PDF to images")
                return None
            
            # Build the vision prompt
            prompt = self.build_vision_prompt(timezone=timezone, fallback_locale=fallback_locale)
            
            logger.info(f"Sending PDF images to Vision API (model: {model})")
            logger.info(f"Number of images: {len(images)}")
            
            # Create OpenAI client
            client = openai.OpenAI(api_key=self.api_key)
            
            # Prepare the message content with images
            content = [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            # Add each image to the content
            for i, image in enumerate(images):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image}",
                        "detail": "high"  # High detail for better text recognition
                    }
                })
            
            # Make the Vision API call
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing ticket/receipt images and extracting structured data to create Apple Wallet passes. Always respond with valid JSON only."
                    },
                    {
                        "role": "user", 
                        "content": content
                    }
                ],
                max_tokens=2000,
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # Extract the response content
            response_text = response.choices[0].message.content
            logger.info(f"LLM response length: {len(response_text)} characters")
            
            # Parse JSON response
            try:
                wallet_pass_data = json.loads(response_text)
                logger.info("✅ Successfully parsed LLM response as JSON")
                
                # Validate the new structured response format
                required_fields = ["category", "category_confidence", "tickets_found", "tickets"]
                
                missing_fields = [field for field in required_fields if field not in wallet_pass_data]
                if missing_fields:
                    logger.warning(f"LLM response missing required fields: {missing_fields}")
                    return None
                
                # Validate tickets array
                tickets = wallet_pass_data.get('tickets', [])
                tickets_found = wallet_pass_data.get('tickets_found', 0)
                
                if len(tickets) != tickets_found:
                    logger.warning(f"Tickets count mismatch: found {len(tickets)}, expected {tickets_found}")
                
                category = wallet_pass_data.get('category', 'Unknown')
                confidence = wallet_pass_data.get('category_confidence', 0.0)
                
                logger.info(f"✅ LLM extracted category: {category} (confidence: {confidence:.2f})")
                logger.info(f"✅ Found {len(tickets)} ticket(s)")
                
                return wallet_pass_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response content: {response_text[:500]}...")
                return None
                
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return None
    
    async def process_pdf_with_vision_to_wallet_passes(self, pdf_path: str, organization: str, 
                                                     pass_type_id: str, team_id: str, 
                                                     timezone: str = "+00:00", fallback_locale: str = "en-US",
                                                     model: str = "gpt-4o") -> Optional[List[Dict[str, Any]]]:
        """
        Process PDF with Vision API and convert directly to Apple Wallet pass format.
        
        This method combines the LLM extraction with category-specific processing
        to return ready-to-use Apple Wallet pass JSON objects.
        
        Args:
            pdf_path: Path to the PDF file
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier  
            team_id: Apple Developer team identifier
            timezone: Timezone offset (e.g., "+03:00")
            fallback_locale: Fallback locale (e.g., "en-US")
            model: OpenAI model to use
            
        Returns:
            List of Apple Wallet pass JSON objects, or None if processing fails
        """
        logger.info("🔄 Processing PDF with Vision API to Apple Wallet passes")
        
        # First, extract structured data using Vision API
        llm_data = await self.process_pdf_with_vision(
            pdf_path, organization, pass_type_id, team_id, timezone, fallback_locale, model
        )
        
        if not llm_data:
            logger.error("❌ Failed to extract data from PDF using Vision API")
            return None
        
        try:
            # Convert LLM structured data to Apple Wallet passes
            logger.info("🔄 Converting LLM data to Apple Wallet pass format")
            wallet_passes = process_llm_data_to_wallet_passes(
                llm_data, organization, pass_type_id, team_id
            )
            
            if wallet_passes:
                logger.info(f"✅ Successfully generated {len(wallet_passes)} Apple Wallet pass(es)")
                return wallet_passes
            else:
                logger.error("❌ No wallet passes were generated from LLM data")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to convert LLM data to wallet passes: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if LLM processor is available and configured."""
        return self.has_openai and self.has_pdf_libs
