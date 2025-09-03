"""
PDF to Apple Wallet Pass Converter Package

A production-ready package that converts arbitrary ticket/receipt-like PDFs 
into Apple Wallet pass.json payloads with deterministic extraction and optional LLM mapping.
"""

__version__ = "1.0.0"
__author__ = "PDF to Wallet Pass Converter"

from .models import TicketData
from .pdf_processor import PDFProcessor
from .qr_detector import QRDetector
from .field_parser import FieldParser
from .pass_builder import PassBuilder
from .llm_mapper import LLMMapper

__all__ = [
    "TicketData",
    "PDFProcessor", 
    "QRDetector",
    "FieldParser",
    "PassBuilder",
    "LLMMapper"
]
