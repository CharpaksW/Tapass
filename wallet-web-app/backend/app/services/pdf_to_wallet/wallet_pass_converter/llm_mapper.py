"""
LLM integration for enhanced field mapping and normalization.
"""

import json
import logging
import os
from typing import Dict, Optional

try:
    import jsonschema
    from .models import LLM_OUTPUT_SCHEMA, TicketData
except ImportError as e:
    raise ImportError(f"Missing required dependency: {e}. Install with: pip install jsonschema")

# Optional LLM dependency
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)


class LLMMapper:
    """Handles LLM-based field mapping and normalization"""
    
    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.has_llm = HAS_ANTHROPIC if provider == "anthropic" else False
        
        if not self.has_llm:
            logger.warning(f"LLM provider '{provider}' not available")
    
    async def map_fields(self, ticket_data: TicketData, api_key_env: str) -> Optional[Dict]:
        """Use LLM to normalize and map fields"""
        if not self.has_llm or self.provider != 'anthropic':
            logger.warning("Anthropic not available or unsupported provider")
            return None
        
        api_key = os.getenv(api_key_env)
        if not api_key:
            logger.warning(f"API key not found in environment variable {api_key_env}")
            return None
        
        try:
            client = anthropic.Anthropic(api_key=api_key)
            
            # Prepare input data (truncate if too long)
            raw_text = ticket_data.raw_text[:16000] if len(ticket_data.raw_text) > 16000 else ticket_data.raw_text
            
            system_message = (
                "You map structured facts from a ticket-like PDF into a strict schema. "
                "Never invent values. Prefer QR payload for barcode_message. "
                "Only use information that is clearly present in the provided text. "
                "The text may contain Hebrew characters - handle Hebrew text properly "
                "and extract Hebrew field names and values accurately. Hebrew text "
                "reads right-to-left but numbers and codes remain left-to-right."
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
            
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system=system_message,
                messages=[{
                    "role": "user",
                    "content": f"Map this ticket data to the schema: {json.dumps(user_content)}"
                }]
            )
            
            # Parse response
            response_text = message.content[0].text
            try:
                llm_result = json.loads(response_text)
                
                # Validate against schema
                jsonschema.validate(llm_result, LLM_OUTPUT_SCHEMA)
                logger.info("LLM mapping successful and validated")
                return llm_result
                
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                logger.warning(f"LLM response validation failed: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"LLM mapping failed: {e}")
            return None
    
    def apply_llm_results(self, ticket_data: TicketData, llm_result: Dict) -> None:
        """Apply LLM results to ticket data"""
        if not llm_result:
            return
            
        for key, value in llm_result.items():
            if value is not None and hasattr(ticket_data, key):
                setattr(ticket_data, key, value)
        
        logger.info("Applied LLM field mapping results")
