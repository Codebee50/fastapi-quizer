from fastapi import UploadFile
import fitz
import ocrmypdf
import tempfile
import os
from typing import Optional

class PDFParser:
    def __init__(self, file_path: Optional[str]=None, file: Optional[UploadFile]=None):
        self.file = file
        self.file_path = file_path
        
    def extract_pdf_text(self):
        if not self.file:
            raise ValueError("File is required")
        extracted_text_dict = self._pymupdf_text_extract()
        
        empty_texts = [text for text in extracted_text_dict.values() if text.strip() == ""]
        if len(empty_texts) > 0.9 * len(extracted_text_dict):
            print("PDF contains more than 90% empty text, using OCR")
            extracted_text_dict = self._ocr_and_extract()
            return extracted_text_dict
        else:
            return extracted_text_dict

        
    def _pymupdf_text_extract(self)-> dict[int, str]:
        pdf_bytes = self.file.file.read()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            full_text = {}
            
            index = 0
            for page in doc:
                full_text[index] = page.get_text("text")
                index += 1
                
            return full_text
        
        
    def _ocr_and_extract(self)-> dict[int, str]:
        # Create temp files
        input_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        output_pdf = tempfile.NamedTemporaryFile(suffix="_ocr.pdf", delete=False)

        try:
            # Reset pointer to start
            self.file.file.seek(0)

            # Read file bytes
            file_bytes = self.file.file.read()

            if not file_bytes:
                raise ValueError("Uploaded file is empty")

            # Write to temp input file
            with open(input_pdf.name, "wb") as f:
                f.write(file_bytes)

            # Run OCR
            ocrmypdf.ocr(input_pdf.name, output_pdf.name, force_ocr=True)

            # Extract text
            doc = fitz.open(output_pdf.name)
            full_text = {}
            index = 0
            for page in doc:
                full_text[index] = page.get_text("text")
                index += 1
            doc.close()

            return full_text

        finally:
            # Cleanup
            for f in [input_pdf.name, output_pdf.name]:
                try:
                    os.unlink(f)
                except FileNotFoundError:
                    pass  # Files might already be deleted