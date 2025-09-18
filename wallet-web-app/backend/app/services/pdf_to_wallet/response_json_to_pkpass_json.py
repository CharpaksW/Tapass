"""
Main processing module for converting LLM extracted data to Apple Wallet pass JSON.

This module coordinates the category-specific processors and handles file I/O.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any

from category_processors import (
    EventTicketProcessor,
    BoardingPassProcessor, 
    StoreCardProcessor,
    GenericTicketProcessor
)

logger = logging.getLogger(__name__)


def process_llm_data_to_wallet_passes(llm_data: Dict[str, Any], organization: str, 
                                    pass_type_id: str, team_id: str, 
                                    output_dir: str = "generated_passes") -> List[Dict[str, Any]]:
    """
    Main function to process LLM extracted data and convert to Apple Wallet passes.
    Automatically saves each ticket as a separate JSON file when multiple tickets are found.
    
    Args:
        llm_data: The structured JSON data from the LLM
        organization: Organization name for the pass
        pass_type_id: Apple Wallet pass type identifier
        team_id: Apple Developer team identifier
        output_dir: Directory to save individual pass files when multiple tickets found # TODO:: making unique per user request
    
    Returns:
        List of Apple Wallet pass JSON objects
    """
    import os
    from pathlib import Path
    
    logger.info(f" Processing LLM data with category: {llm_data.get('category', 'Unknown')}")
    
    # Extract category and tickets from LLM data
    category = llm_data.get('category', '').strip()
    tickets = llm_data.get('tickets', [])
    
    if not tickets:
        logger.warning("No tickets found in LLM data")
        return []
    
    # Route to appropriate processor based on LLM category
    # LLM categories: ["Boarding pass","Coupon","Event ticket","Store card","Generic"]
    if category == "Event ticket":
        processor = EventTicketProcessor(organization, pass_type_id, team_id)
        passes = processor.process_event_tickets(tickets, llm_data)
    elif category == "Boarding pass":
        processor = BoardingPassProcessor(organization, pass_type_id, team_id)
        passes = processor.process_boarding_passes(tickets, llm_data)
    elif category in ["Store card", "Coupon"]:
        processor = StoreCardProcessor(organization, pass_type_id, team_id)
        passes = processor.process_store_cards(tickets, llm_data)
    elif category == "Generic":
        processor = GenericTicketProcessor(organization, pass_type_id, team_id)
        passes = processor.process_generic_tickets(tickets, llm_data)
    else:
        # Fallback for unknown categories or legacy support
        logger.warning(f"Unknown category '{category}', using generic processor")
        processor = GenericTicketProcessor(organization, pass_type_id, team_id)
        passes = processor.process_generic_tickets(tickets, llm_data)
    
    logger.info(f"✅ Generated {len(passes)} Apple Wallet pass(es)")
    
    # Always save tickets as separate files
    if len(passes) >= 1:
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        saved_files = []
        
        if len(passes) > 1:
            logger.info(f" Multiple tickets detected ({len(passes)}), saving each as separate JSON file...")
        else:
            logger.info(f" Single ticket detected, saving as JSON file...")
        
        for i, pass_data in enumerate(passes, 1):
            try:
                # Create a subdirectory for each pass
                pass_dir = output_path / str(i)
                pass_dir.mkdir(exist_ok=True)
                
                # Save the pass as a single JSON object (not array)
                pass_file = pass_dir / "pass.json"
                
                with open(pass_file, 'w', encoding='utf-8') as f:
                    json.dump(pass_data, f, indent=2, ensure_ascii=False)
                
                saved_files.append(str(pass_file))
                
                # Log details about the saved pass
                description = pass_data.get('description', 'Unknown')
                serial = pass_data.get('serialNumber', 'N/A')
                logger.info(f"💾 Pass {i}/{len(passes)}: {description} → {pass_file}")
                logger.info(f"   Serial: {serial}")
                
            except Exception as e:
                logger.error(f"❌ Failed to save pass {i}: {e}")
                continue
        
        logger.info(f"✅ Successfully saved {len(saved_files)} pass file(s) to {output_path.absolute()}")
    
    return passes
