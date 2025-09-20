
from fastapi import APIRouter, HTTPException

from services.chromadb_service import ChromadbService


router = APIRouter()

chroma_service = ChromadbService()

@router.post("/add_documents_simple")
async def add_documents():
        try:
            await chroma_service.add_simple_document("test")
            return {"status": "success", "message": "Documents added successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error adding documents: {str(e)}")

@router.get("/get_document")
async def get_document(query: str):
    try:
        await chroma_service.search_documents(query)
        return {"status": "success", "message": "Documents added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding documents: {str(e)}")