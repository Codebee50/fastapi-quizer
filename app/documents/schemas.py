from pydantic import BaseModel, Field
from typing import Literal

class ParseDocumentToTextSchema(BaseModel):
    file_url: str = Field(..., description="The url of the file to parse to text")
    file_type: Literal["application/pdf", "application/docx", "application/doc"] = Field(..., description="The type of the file to parse to text")