from pydantic import BaseModel
from typing import List, Optional

class DriveItem(BaseModel):
    """Represents a file or folder in Google Drive."""
    id: str
    name: str
    mimeType: str
    webViewLink: str

class PermissionDetails(BaseModel):
    """Represents a specific permission on a Drive item."""
    id: str
    type: str # 'user', 'group', 'domain', 'anyone'
    role: str # 'owner', 'organizer', 'fileOrganizer', 'writer', 'commenter', 'reader'
    emailAddress: Optional[str] = None

class FilePermissions(BaseModel):
    """Represents a file along with its complete list of permissions."""
    file: DriveItem
    permissions: List[PermissionDetails]