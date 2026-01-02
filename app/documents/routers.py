
from fastapi import APIRouter
from app.documents.schemas import ParseDocumentToTextSchema
router = APIRouter()

@router.post("/parse-to-text/")
async def parse_document_to_text(request: ParseDocumentToTextSchema):
    pass
