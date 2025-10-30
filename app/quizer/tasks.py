import json
from tempfile import NamedTemporaryFile
from typing import Optional
from agents.items import TResponseOutputItem
from celery import shared_task
import asyncio
from agents import Agent, TResponseInputItem, function_tool, Runner
from pydantic import BaseModel
from itertools import chain
from itertools import chain
from fpdf import FPDF
import uuid
from io import BytesIO
import cloudinary
import cloudinary.uploader
import os
import requests
from botocore.exceptions import ClientError

from app import config
from app.quizer.services import PDFParser

import logging


logger = logging.getLogger(__name__)


MAX_FILE_SIZE_MB = 50



SYSTEM_PROMPT = """
    You are a precise and reliable quiz generation assistant for educational and professional content.

    Your task is to generate multiple-choice questions (MCQs) based *strictly* on the provided text content.
    Each item in the input list represents one page of a document (e.g., a government rulebook, policy, or training manual).

    ### Rules
    1. Do **not hallucinate** or infer information not explicitly stated in the text.
    2. Ignore the page by returning an empty list if you think it is not relevant to the quiz generation e.g preliminary pages, table of contents, index, etc.
    2. Focus on important facts, definitions, processes, or key ideas.
    3. Avoid repeating the same question across pages.
    4. Each question should:
    - Have exactly **4 options (A-D)**.
    - Have **one correct answer** clearly supported by the text.
    - Be **self-contained** (understandable without context from other pages).
    5. Skip pages that contain no meaningful or relevant content.
    6. If the page is a valid page, then generate a minimum of 5 questions per page

    ### Output Format
    Return the result as a JSON array of question objects:

    [
        {
            "question": "string",
            "options": ["A", "B", "C", "D"],
            "answer": "A",
            "explanation": "string (briefly explaining why the answer is correct, if possible)"
        }
    ]

    ### Example
    Input Page:
    "According to the Public Service Rules (PSR), a junior officer refers to a pensionable officer on GL.06 and below."

    Output:
    [
        {
            "question": "According to the Public Service Rules, who is classified as a junior officer?",
            "options": [
                "An officer on GL.06 and below",
                "An officer on GL.07 and above",
                "A contract staff member",
                "A political appointee"
            ],
            "answer": "An officer on GL.06 and below",
            "explanation": "The PSR defines a junior officer as a pensionable officer on GL.06 and below."
        }
    ]
"""


def send_brevo_email(email, subject, html_content):
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.BREVO_API_KEY}", # this is the api key for the brevo api
            "accept": "application/json",
            "api-key": config.BREVO_API_KEY
        },
        json={
            "to": [{"email": email}],
            "subject": subject,
            "htmlContent": html_content,
            "sender": {
                "name": "BeeQuizer",
                # "email": "support@erdvsion.dev"
                "email": config.BREVO_FROM_EMAIL
            }
        }
    )
    try:
        return response.json()
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return None
        
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str

class QuizBatch(BaseModel):
    questions: list[QuizQuestion]
    

class PdfConverter():
    def __init__(self, questions: list[QuizQuestion]):
        self.questions = questions
        
        option_index_mapping = {
            0: "A",
            1: "B",
            2: "C",
            3: "D",
        }
        self.option_index_mapping = option_index_mapping
    
    def safe_multi_cell(self, pdf, text:str):
        text = str(text) if text is not None else ""
        
        text = text.encode('latin-1', 'replace').decode('latin-1')
        return pdf.multi_cell(0, 5, text, align='L')
    
    def upload_to_cloudinary(self, path:str)-> str | None:
        logger.info("Uploading pdf quizes to cloudinary...")
        try:        
            response = cloudinary.uploader.upload(
                path, 
                public_id=f"quiz_{uuid.uuid4()}",
                resource_type="raw",
                mime_type="application/pdf",
                overwrite=True,
                tags=["beequizer", "quiz"],
                folder="beequizer/quizes",
            )
            
            logger.info("Removing local pdf file")
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"Error uploading to cloudinary: {e}")
            return None
    
    def upload_to_s3(self, path:str)-> str | None:
        logger.info(f"Uploading pdf quizes to s3: {path}")
        
        s3_client = config.get_s3_client()
        
        key = f"results/quiz_{uuid.uuid4()}.pdf"
        try:
            s3_client.put_object(
                Bucket=config.AWS_STORAGE_BUCKET_NAME,
                Key=key,
                Body=open(path, "rb"),
                ContentType="application/pdf",
            )
            
            file_url  = f"https://{config.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
            logger.info(f"Uploaded pdf quizes to s3: {file_url}")
            
            if os.path.exists(path):
                os.remove(path)
            return file_url     
        except Exception as e:
            logger.error(f"Error uploading to s3: {e}")
            return None
        
 
        
    def convert_to_pdf(self):
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(10, 10, 10)
        
        pdf.add_page()
        for index, question in enumerate(self.questions):
            pdf.set_font("Arial", style="B", size=13)
            self.safe_multi_cell(pdf, f"Question {index + 1}:")
            
            pdf.set_font("Arial", style="B", size=11)
            self.safe_multi_cell(pdf, question.question)
            pdf.set_font("Arial", size=11)
            for index, option in enumerate(question.options):
                text_option = self.option_index_mapping.get(index, "UNKNOWN")
                self.safe_multi_cell(pdf, f"({text_option}) {option}")
            self.safe_multi_cell(pdf, f"Answer: {question.answer}")
            self.safe_multi_cell(pdf, f"Explanation: {question.explanation}")
            pdf.ln(10)
        
        file_name = f"quiz_{uuid.uuid4()}.pdf"
        pdf.output(file_name)
        return file_name
    
class SummarizerInputItem(BaseModel):
    text: str

summarizer_agent = Agent(
    name="Summarizer Agent",
    instructions=SYSTEM_PROMPT,
    model="gpt-4o-mini",
    output_type=QuizBatch,
)


async def agent_processor(agent:Agent, task_queue:asyncio.Queue):
    results = []
    while True:
        page_list = await task_queue.get()
        if page_list is None:
            logger.info("Received sentinel, stopping agent processor")
            break
        
        logger.info("Running agent on pages")
        
        # INSERT_YOUR_CODE
        dummy_quiz_batch = QuizBatch(
            questions=[
                QuizQuestion(
                    question="What is the capital of France?",
                    options=["Paris", "London", "Berlin", "Madrid"],
                    answer="Paris",
                    explanation="Paris is the capital and most populous city of France."
                ),
                QuizQuestion(
                    question="Which planet is known as the Red Planet?",
                    options=["Earth", "Mars", "Jupiter", "Venus"],
                    answer="Mars",
                    explanation="Mars is often called the 'Red Planet' because of its reddish appearance."
                )
            ]
        )
        results.extend(dummy_quiz_batch.questions)
        
        
        # result = await Runner.run(agent, json.dumps(page_list, default=str))
        # results.extend(result.final_output.questions)
    return results


async def _generate_quiz_async(text_list: list[str], email: str):
    logger.info("Initiating quiz generation...")

    task_queue = asyncio.Queue()

    MAX_PAGES_PER_AGENT = 10
    MAX_AGENTS = 3

    logger.info("Adding tasks to queue...")
    for i in range(0, len(text_list), MAX_PAGES_PER_AGENT):
        await task_queue.put(text_list[i:i+MAX_PAGES_PER_AGENT])

    for _ in range(MAX_AGENTS):
        await task_queue.put(None)  # sentinel for each worker
        
    logger.info(f"Text list length: {len(text_list)}")
    logger.info(f"Task queue size: {task_queue.qsize()}")
    logger.info(f"Inserted {MAX_AGENTS} sentinels, starting agent processors")

    # Run multiple agent processors concurrently
    results = await asyncio.gather(
        *[agent_processor(summarizer_agent, task_queue) for _ in range(MAX_AGENTS)]
    )
    
    results = list(chain(*results))#this will contain a list of quiz questions
    

    pdf_converter = PdfConverter(results)
    pdf_path = pdf_converter.convert_to_pdf()

    s3_url = pdf_converter.upload_to_s3(pdf_path)
    
    if s3_url:
        html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width:500px; margin:32px auto; border-radius:12px; border:1px solid #e0e0e0;">
                <div style="background: #38a169; color: #fff; padding: 32px 20px 16px 20px; border-radius:12px 12px 0 0;">
                    <h2 style="margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -1px;">Your Quiz is Ready!</h2>
                </div>
                <div style="padding: 24px 20px 32px 20px; background: #f9fafb; border-radius:0 0 12px 12px;">
                    <p style="font-size: 1.1rem; margin-bottom: 24px;">
                        Thank you for using <strong>BeeQuizer</strong>.<br>
                        Your personalized quiz PDF has been generated and is ready to download!
                    </p>
                    <a href="{s3_url}" 
                        style="
                            display: inline-block; 
                            background: #38a169;
                            color: #fff; 
                            font-weight: bold; 
                            padding: 14px 32px; 
                            border-radius: 6px; 
                            font-size: 1.1rem; 
                            text-decoration:none;">
                        Download Your Quiz
                    </a>
                    <p style="font-size:0.96rem;color:#686c72;margin-top:24px;">
                        Need to generate another quiz? JHead over to <a href="https://beequizer.site/">BeeQuizer</a> to get started! <br>
                        Contact the software developer at <a href="mailto:onuhudoudo@gmail.com">onuhudoudo@gmail.com</a> for any questions or feedback.
                    </p>
                </div>
            </div>
        """
        send_brevo_email(email, "Your Quiz is Ready", html_content)
    return "Quiz generated successfully"

@shared_task
def generate_quiz(text_list: list[str], email: str)-> str:
    asyncio.run(_generate_quiz_async(text_list, email))
    return "Quiz generated successfully"

@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
def generate_quiz_from_s3_key(self,file_key:str, email:Optional[str]=None)-> str:
    s3_client = config.get_s3_client()
    
    logger.info(f"Fetching metadata for file {file_key}")
    response = s3_client.head_object(Bucket=config.AWS_STORAGE_BUCKET_NAME, Key=file_key)
    
    file_size_mb = response['ContentLength'] / (1024 * 1024)
    logger.info(f"File size: {file_size_mb}MB")
    if file_size_mb > MAX_FILE_SIZE_MB:
        error_message = f"File size is too large: {file_size_mb}MB, max allowed is {MAX_FILE_SIZE_MB}MB"
        logger.error(error_message)
        return {"success": False, "error": error_message}
    
    logger.info(f"Starting quiz generation from s3 key for {file_key}")
    with NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
        try:
            s3_client.download_fileobj(Bucket=config.AWS_STORAGE_BUCKET_NAME, Key=file_key, Fileobj=tmp_file)
            tmp_file.seek(0)
            
            logger.info(f"Downloaded file from s3: {tmp_file.name}, reading content...")
            
            parser = PDFParser(file=tmp_file)
            extracted_text_dict = parser.extract_pdf_text()
                  
            logger.info(f"Text extraction completed successfully")
            
            generate_quiz.delay(list(extracted_text_dict.values()), email)
            
            logger.info(f"Quiz generation task started successfully")
            return {"success": True, "message": "Quiz generation task started successfully"}
        except ClientError as e:
            logger.error(f"Error downloading file from s3: {e}, retrying...")
            raise self.retry(countdown=2**self.request.retries, max_retries=3)
        except Exception as e:
            logger.error(f"Error processing file: {e}, retrying...")
            
      

@shared_task
def parse_pdf_and_generate_quiz(file_path:str, email:str)-> str:
    logger.info(f"Starting pdf parsing for {file_path}")
    
    parser = PDFParser(file_path=file_path)
    extracted_text_dict = parser.pymupdf_text_extract()
    
    generate_quiz.delay(list(extracted_text_dict.values()), email)
    return "PDF parsed successfully"
    
    
