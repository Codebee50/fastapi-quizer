from typing import Literal
from pydantic import BaseModel, Field

class ParseDocumentToTextSchema(BaseModel):
    file_url: str = Field(..., description="The url of the file to parse to text")
    file_type: Literal["application/pdf", "application/docx", "application/doc"] = Field(..., description="The type of the file to parse to text")

class GeneratePresignedUrlSchema(BaseModel):
    file_name: str = Field(..., description="The name of the file to upload")
    file_type: Literal["application/pdf", "application/docx", "application/doc"] = Field(..., description="The type of the file to upload")

class GenerateQuizFromS3KeySchema(BaseModel):
    s3_key: str = Field(..., description="The key of the file to generate quiz from")
    email: str = Field(..., description="The email of the user to send the quiz to")