import fitz
from pymupdf import Document
from src.models.structured_document import *
from src.type_parser.utils import *

class PDFParser:
    """Извлекает текст, шрифты и координаты из PDF."""
    def parse(self, pdf_path: str):
        doc = fitz.open(pdf_path)
        return doc