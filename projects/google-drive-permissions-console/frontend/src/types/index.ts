export interface DriveItem {
  id: string;
  name: string;
  mimeType: string;
  webViewLink: string;
}

export interface PermissionDetails {
  id: string;
  type: 'user' | 'group' | 'domain' | 'anyone';
  role: 'owner' | 'organizer' | 'fileOrganizer' | 'writer' | 'commenter' | 'reader';
  emailAddress?: string;
}

export interface FilePermissions {
  file: DriveItem;
  permissions: PermissionDetails[];
}