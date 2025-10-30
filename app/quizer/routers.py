import tempfile
import boto3
from fastapi import APIRouter, File, UploadFile
from fastapi.exceptions import HTTPException
from app.quizer.schemas import GeneratePresignedUrlSchema, GenerateQuizFromS3KeySchema
from app.quizer.services import PDFParser
from app.quizer.tasks import generate_quiz, generate_quiz_from_s3_key, parse_pdf_and_generate_quiz
from app import config
router = APIRouter()
import uuid


@router.post("/upload/presigned-url/")
async def generate_upload_presigned_url(request: GeneratePresignedUrlSchema ):
    s3_client = config.get_s3_client()
    
    file_key = f"uploads/{uuid.uuid4()}"
    presigned_url = s3_client.generate_presigned_url("put_object", Params={
        "Bucket": config.AWS_STORAGE_BUCKET_NAME, 
        "Key": file_key,
        "ContentType": request.file_type
    })
    return {"presigned_url": presigned_url, "file_key": file_key}


@router.post("/generate/from-s3-key/")
async def process_uploaded_file(request: GenerateQuizFromS3KeySchema):    
    task = generate_quiz_from_s3_key.delay(request.s3_key, request.email)
    return {"message": "Quiz generation task started successfully", "task_id": task.id}


@router.post("/generate/")
async def initiate_quiz_generation(email: str, file: UploadFile = File(...)):
    file_extension = file.filename.split(".")[-1]
    if file_extension != "pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")


    parser = PDFParser(file)
    extracted_text_dict = parser.extract_pdf_text()
    
    if len(extracted_text_dict) > 300:
        raise HTTPException(status_code=400, detail="PDF contains more than 300 pages, please use a smaller file")
    
    task = generate_quiz.delay(list(extracted_text_dict.values()), email)
    return {"message": "PDF parsed successfully", "task_id": task.id}

    