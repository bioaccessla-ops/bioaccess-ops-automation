from fastapi import APIRouter
from app.api.v1.endpoints import files

api_router = APIRouter()

# Include routers from different endpoint files
api_router.include_router(files.router, prefix="/files", tags=["Files"])