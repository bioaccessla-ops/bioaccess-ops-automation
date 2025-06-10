from fastapi import APIRouter, HTTPException, status
from app.models.drive import FilePermissions
from app.services.google_drive import drive_service

router = APIRouter()

@router.get(
    "/{file_id}/permissions",
    response_model=FilePermissions,
    summary="Get Permissions for a Specific File"
)
def get_permissions_for_file(file_id: str):
    """
    Retrieves the metadata and all associated permissions for a given file ID.
    """
    permissions = drive_service.get_file_permissions(file_id)
    if not permissions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )
    return permissions