from fastapi import UploadFile
import fitz
import ocrmypdf
import tempfile
import os

class PDFParser:
    def __init__(self, file: UploadFile):
        self.file = file
    
    def pymupdf_text_extract(self):
        pdf_bytes = self.file.file.read()
        
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            full_text = {}
            
            index = 0
            for page in doc:
                full_text[index] = page.get_text("text")
                index += 1
                
            return full_text
        
    def ocr_and_extract(self):
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