import React, { useState } from 'react';
import driveApi from '../api/driveApi';
import type { FilePermissions } from '../types';

const FolderView: React.FC = () => {
  const [permissions, setPermissions] = useState<FilePermissions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchPermissions = async (fileId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await driveApi.get<FilePermissions>(`/files/${fileId}/permissions`);
      setPermissions(response.data);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message;
      setError(`Failed to fetch permissions: ${errorMessage}`);
      setPermissions(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Folder View</h1>
      <p>This view will show a file tree and permission details.</p>

      <button onClick={() => fetchPermissions('file1')} disabled={loading}>
        {loading ? 'Loading...' : 'Fetch Permissions for "requirements.docx" (Mock)'}
      </button>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {permissions && (
        <div style={{ marginTop: '20px', border: '1px solid #ccc', padding: '10px' }}>
          <h3>Permissions for: {permissions.file.name}</h3>
          <ul>
            {permissions.permissions.map(p => (
              <li key={p.id}>
                <strong>{p.emailAddress || p.type}</strong> ({p.role})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default FolderView;