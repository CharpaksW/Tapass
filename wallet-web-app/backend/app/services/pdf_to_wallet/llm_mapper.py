"""
LLM integration for enhanced field mapping and normalization.
"""

import json
import logging
import os
import re
import time
import random
from typing import Dict, Optional

try:
    import jsonschema
    from .models import LLM_OUTPUT_SCHEMA, TicketData
except ImportError as e:
    raise ImportError(f"Missing required dependency: {e}. Install with: pip install jsonschema")

# OpenAI dependency
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logger = logging.getLogger(__name__)


class LLMMapper:
    """Handles LLM-based field mapping and normalization"""
    
    # Class-level rate limiting state
    _last_request_time = 0
    _min_interval = 22  # Minimum seconds between requests (conservative for free tier)
    
    def __init__(self):
        self.provider = "openai"
        self.has_llm = HAS_OPENAI
            
        if not self.has_llm:
            logger.warning("OpenAI provider not available")
    
    async def map_fields(self, ticket_data: TicketData, api_key_env: str) -> Optional[Dict]:
        """Use LLM to normalize and map fields"""
        if not self.has_llm:
            logger.warning(f"LLM provider '{self.provider}' not available")
            return None
        
        api_key = os.getenv(api_key_env)
        if not api_key:
            logger.warning(f"API key not found in environment variable {api_key_env}")
            return None
            
        # Diagnostic logging for API key (safely)
        if api_key:
            key_preview = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
            logger.info(f"Using API key: {key_preview} (length: {len(api_key)})")
            
            # Validate API key format
            if not api_key.startswith('sk-'):
                logger.error(f"Invalid API key format - should start with 'sk-', got: {api_key[:10]}...")
                return None
        
        try:
            # Prepare input data (more aggressive truncation for rate limits)
            # Free tier has token limits, so be more conservative
            max_chars = 8000  # Roughly 2000 tokens, leaving room for response
            raw_text = ticket_data.raw_text[:max_chars] if len(ticket_data.raw_text) > max_chars else ticket_data.raw_text
            if len(ticket_data.raw_text) > max_chars:
                logger.info(f"Truncated text from {len(ticket_data.raw_text)} to {max_chars} characters for rate limit management")
            
            system_message = (
                "You are a ticket classification and PKPass data extraction expert. "
                "Analyze the raw text extracted from a PDF and:\n\n"
                "1. CLASSIFY the ticket type based on content:\n"
                "   - 'eventTicket': Concerts, sports, theater, shows, conferences\n"
                "   - 'boardingPass': Flights, trains, buses, ferries\n"
                "   - 'storeCard': Loyalty cards, membership cards\n"
                "   - 'coupon': Discounts, vouchers, promotional offers\n"
                "   - 'generic': Any other type of ticket/pass\n\n"
                "2. EXTRACT key information for PKPass wallet format:\n"
                "   - title: Main event/service name (required)\n"
                "   - serial: Ticket number, booking reference, or unique identifier\n"
                "   - barcode_message: QR code content or main barcode data\n"
                "   - datetime: Event date/time in ISO format (YYYY-MM-DDTHH:MM:SS)\n"
                "   - venue: Location, airport, station, or venue name\n"
                "   - auditorium: Hall, gate, platform within venue\n"
                "   - seat: Seat number, row, or seating assignment\n"
                "   - name: Passenger/attendee name if present\n"
                "   - flight: Flight number, train number, or service identifier\n"
                "   - pnr: Passenger Name Record for flights\n"
                "   - origin: Departure location for transportation\n"
                "   - destination: Arrival location for transportation\n\n"
                "RULES:\n"
                "- Only extract information clearly present in the text\n"
                "- Prefer QR payload data for barcode_message\n"
                "- Handle Hebrew/RTL text properly (Hebrew text reads right-to-left)\n"
                "- Return ONLY valid JSON matching the schema\n"
                "- Your response must start with { and end with }"
            )
            
            return await self._map_with_openai(api_key, system_message, ticket_data, raw_text)
                
        except Exception as e:
            logger.warning(f"LLM mapping failed: {e}")
            return None
    
    async def _map_with_openai(self, api_key: str, system_message: str, ticket_data: TicketData, raw_text: str) -> Optional[Dict]:
        """Handle OpenAI API integration"""
        # Simple client initialization - only pass api_key
        client = openai.OpenAI(api_key=api_key)
        
        # Global rate limiting across all instances (for concurrent testing)
        current_time = time.time()
        time_since_last = current_time - LLMMapper._last_request_time
        
        if time_since_last < LLMMapper._min_interval:
            wait_time = LLMMapper._min_interval - time_since_last + random.uniform(0, 2)
            logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds since last request")
            time.sleep(wait_time)
        
        LLMMapper._last_request_time = time.time()
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using GPT-4o-mini for better rate limits and lower cost
                max_tokens=1000,
                temperature=0.1,  # Low temperature for consistent, factual responses
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user", 
                        "content": f"Analyze this raw PDF text and classify the ticket, then extract PKPass data:\n\nRAW TEXT:\n{raw_text}\n\nQR CODE PAYLOADS:\n{json.dumps(ticket_data.qr_payloads)}\n\nDETECTED PATTERNS:\n- Dates: {json.dumps(ticket_data.dates)}\n- Numbers: {json.dumps(ticket_data.numbers)}\n- Codes: {json.dumps(ticket_data.codes)}\n\nReturn JSON with proper classification and extracted fields:"
                    }
                ]
            )
        except Exception as api_error:
            # Enhanced error diagnosis
            error_str = str(api_error)
            logger.error(f"OpenAI API Error Details: {error_str}")
            
            # Check for specific error types
            if "429" in error_str:
                if "quota" in error_str.lower() or "billing" in error_str.lower():
                    logger.error("🚨 ACCOUNT ISSUE: Quota exceeded or billing problem!")
                    logger.error("👉 Check your OpenAI account balance and billing at https://platform.openai.com/account/billing")
                    return None
                elif "rate_limit" in error_str.lower():
                    logger.warning("Rate limit exceeded, implementing exponential backoff...")
                    
                    # Exponential backoff with jitter: wait longer each time
                    for attempt in range(3):  # Max 3 retries
                        backoff_time = (2 ** attempt) * 30 + random.uniform(0, 10)  # 30s, 60s, 120s + jitter
                        logger.info(f"Waiting {backoff_time:.1f} seconds before retry attempt {attempt + 1}/3")
                        time.sleep(backoff_time)
                        
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                max_tokens=800,  # Slightly reduce tokens to help with limits
                                temperature=0.1,
                                messages=[
                                    {
                                        "role": "system",
                                        "content": system_message
                                    },
                                {
                                    "role": "user",
                                    "content": f"Analyze this raw PDF text and classify the ticket, then extract PKPass data:\n\nRAW TEXT:\n{raw_text}\n\nQR CODE PAYLOADS:\n{json.dumps(ticket_data.qr_payloads)}\n\nDETECTED PATTERNS:\n- Dates: {json.dumps(ticket_data.dates)}\n- Numbers: {json.dumps(ticket_data.numbers)}\n- Codes: {json.dumps(ticket_data.codes)}\n\nReturn JSON with proper classification and extracted fields:"
                                }
                                ]
                            )
                            logger.info(f"Retry attempt {attempt + 1} successful!")
                            break  # Success, exit retry loop
                        except Exception as retry_error:
                            if attempt == 2:  # Last attempt
                                logger.error(f"All retry attempts failed: {retry_error}")
                                return None
                            logger.warning(f"Retry attempt {attempt + 1} failed: {retry_error}")
                else:
                    logger.error("🚨 UNKNOWN 429 ERROR - This may indicate account or IP issues")
                    return None
            elif "401" in error_str or "unauthorized" in error_str.lower():
                logger.error("🚨 AUTHENTICATION ERROR: Invalid API key!")
                logger.error("👉 Check your API key at https://platform.openai.com/api-keys")
                return None
            elif "403" in error_str or "forbidden" in error_str.lower():
                logger.error("🚨 ACCESS FORBIDDEN: API key may not have access to this model")
                return None
            else:
                logger.error(f"🚨 UNEXPECTED API ERROR: {api_error}")
                return None
        
        # Parse response with enhanced error handling
        response_text = response.choices[0].message.content
        
        # Check for empty or None response
        if not response_text:
            logger.error("🚨 OpenAI returned empty response")
            logger.error("This may indicate:")
            logger.error("- Content filtering blocked the response")
            logger.error("- API quota/rate limit issues")
            logger.error("- Model output truncation")
            return None
        
        # Log response for debugging (first 200 chars)
        logger.debug(f"OpenAI response preview: {response_text[:200]}...")
        
        try:
            # Try to parse JSON
            llm_result = json.loads(response_text)
            
            # Validate against schema
            jsonschema.validate(llm_result, LLM_OUTPUT_SCHEMA)
            logger.info("OpenAI LLM mapping successful and validated")
            return llm_result
            
        except json.JSONDecodeError as e:
            logger.error(f"🚨 JSON parsing failed: {e}")
            logger.error(f"Raw response: '{response_text}'")
            logger.error("This suggests the AI returned non-JSON content")
            
            # Try to extract JSON from response if it's wrapped in text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    extracted_json = json_match.group(0)
                    llm_result = json.loads(extracted_json)
                    jsonschema.validate(llm_result, LLM_OUTPUT_SCHEMA)
                    logger.info("✅ Recovered JSON from wrapped response")
                    return llm_result
                except (json.JSONDecodeError, jsonschema.ValidationError):
                    logger.error("❌ Failed to extract valid JSON from response")
            
            return None
            
        except jsonschema.ValidationError as e:
            logger.error(f"🚨 Schema validation failed: {e}")
            logger.error(f"Response content: {response_text}")
            logger.error("The AI returned valid JSON but it doesn't match the expected schema")
            return None
    
    
    def apply_llm_results(self, ticket_data: TicketData, llm_result: Dict) -> None:
        """Apply LLM results to ticket data"""
        if not llm_result:
            return
            
        for key, value in llm_result.items():
            if value is not None and hasattr(ticket_data, key):
                setattr(ticket_data, key, value)
        
        logger.info("Applied LLM field mapping results")
