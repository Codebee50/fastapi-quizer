from fastapi import APIRouter, File, UploadFile
from fastapi.exceptions import HTTPException
from app.quizer.services import PDFParser
from app.quizer.tasks import generate_quiz
router = APIRouter()

@router.post("/quiz/generate/")
def initiate_quiz_generation(email: str, file: UploadFile = File(...)):
    file_extension = file.filename.split(".")[-1]
    if file_extension != "pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    parser = PDFParser(file)
    extracted_text_dict = parser.pymupdf_text_extract()
    
    empty_texts = [text for text in extracted_text_dict.values() if text.strip() == ""]
    if len(empty_texts) > 0.9 * len(extracted_text_dict):
        print("PDF contains more than 90% empty text, using OCR")
        extracted_text_dict = parser.ocr_and_extract()
    
    if len(extracted_text_dict) > 300:
        raise HTTPException(status_code=400, detail="PDF contains more than 300 pages, please use a smaller file")
    
    # task = generate_quiz.delay(list(extracted_text_dict.values()), email)
    return {"message": "PDF parsed successfully", "task_id": "task.id"}

    