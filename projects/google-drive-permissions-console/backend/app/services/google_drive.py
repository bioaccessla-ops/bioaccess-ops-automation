# This file will eventually contain all the logic for making
# authenticated calls to the Google Drive API.

# For now, we use mock data to allow the frontend to be built.

from app.models.drive import DriveItem, PermissionDetails, FilePermissions

# Mock database of files and folders
MOCK_DRIVE_DATA = {
    "root": DriveItem(id="root", name="My Drive", mimeType="application/vnd.google-apps.folder", webViewLink="#"),
    "folder1": DriveItem(id="folder1", name="Project Alpha", mimeType="application/vnd.google-apps.folder", webViewLink="#"),
    "file1": DriveItem(id="file1", name="requirements.docx", mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document", webViewLink="#"),
}

MOCK_PERMISSIONS_DATA = {
    "file1": FilePermissions(
        file=MOCK_DRIVE_DATA["file1"],
        permissions=[
            PermissionDetails(id="perm1", type="user", role="owner", emailAddress="admin@example.com"),
            PermissionDetails(id="perm2", type="user", role="writer", emailAddress="developer1@example.com"),
            PermissionDetails(id="perm3", type="anyone", role="reader"),
        ]
    )
}

class DriveService:
    """
    A service class to interact with Google Drive API.
    """
    def get_file_permissions(self, file_id: str) -> FilePermissions:
        """
        Fetches a file and its associated permissions.
        
        TODO: Replace mock data with a real Google Drive API call.
        """
        # Simulate fetching data
        if file_id in MOCK_PERMISSIONS_DATA:
            return MOCK_PERMISSIONS_DATA[file_id]
        return None

drive_service = DriveService()