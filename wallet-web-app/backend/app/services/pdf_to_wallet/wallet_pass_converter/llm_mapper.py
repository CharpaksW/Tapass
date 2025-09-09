"""
LLM integration for enhanced field mapping and normalization.
"""

import json
import logging
import os
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
                "You map structured facts from a ticket-like PDF into a strict schema. "
                "Never invent values. Prefer QR payload for barcode_message. "
                "Only use information that is clearly present in the provided text. "
                "The text may contain Hebrew characters - handle Hebrew text properly "
                "and extract Hebrew field names and values accurately. Hebrew text "
                "reads right-to-left but numbers and codes remain left-to-right. "
                "Return only valid JSON that matches the expected schema."
            )
            
            user_content = {
                "raw_text": raw_text,
                "qr_payloads": ticket_data.qr_payloads,
                "candidates": {
                    "dates": ticket_data.dates,
                    "numbers": ticket_data.numbers,
                    "codes": ticket_data.codes
                }
            }
            
            return await self._map_with_openai(api_key, system_message, user_content)
                
        except Exception as e:
            logger.warning(f"LLM mapping failed: {e}")
            return None
    
    async def _map_with_openai(self, api_key: str, system_message: str, user_content: Dict) -> Optional[Dict]:
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
                        "content": f"Map this ticket data to the schema: {json.dumps(user_content)}"
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
                                        "content": f"Map this ticket data to the schema: {json.dumps(user_content)}"
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
        
        # Parse response
        response_text = response.choices[0].message.content
        try:
            llm_result = json.loads(response_text)
            
            # Validate against schema
            jsonschema.validate(llm_result, LLM_OUTPUT_SCHEMA)
            logger.info("OpenAI LLM mapping successful and validated")
            return llm_result
            
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            logger.warning(f"OpenAI LLM response validation failed: {e}")
            return None
    
    
    def apply_llm_results(self, ticket_data: TicketData, llm_result: Dict) -> None:
        """Apply LLM results to ticket data"""
        if not llm_result:
            return
            
        for key, value in llm_result.items():
            if value is not None and hasattr(ticket_data, key):
                setattr(ticket_data, key, value)
        
        logger.info("Applied LLM field mapping results")
