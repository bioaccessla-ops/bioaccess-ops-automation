# Google Drive Permissions Management Console

This document outlines the project architecture, technology stack, and development plan for the Google Drive Permissions Management Console. This web application will provide administrators with a user-friendly interface to audit and manage file and folder permissions within Google Drive, replacing several command-line scripts.

---

## **Technology Stack** ⚙️

-   **Backend**: **Python 3.11+** with the **FastAPI** framework.
-   **Frontend**: **React 18+** with **Vite** and **TypeScript**.
-   **Data Fetching**: The **`axios`** library will be used for client-server communication.

---

## **Project Structure** 📁

The project uses a monorepo structure to house both the backend and frontend code in a single repository.

```plaintext
google-drive-permissions-console/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app instance and router setup
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── files.py    # Endpoints for file/folder permissions
│   │   │       │   └── users.py    # Endpoints for user-centric permissions
│   │   │       └── router.py     # Aggregates all v1 endpoints
│   │   ├── core/
│   │   │   └── config.py         # Application settings (env variables)
│   │   ├── models/
│   │   │   ├── permissions.py    # Pydantic models for permission data
│   │   │   └── drive.py          # Pydantic models for file/folder data
│   │   └── services/
│   │       └── google_drive.py   # Logic to interact with Google Drive API
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── driveApi.ts       # Axios instance and API call functions
│   │   ├── components/
│   │   │   ├── common/           # Reusable components (Button, Modal, etc.)
│   │   │   ├── layout/           # Main layout components (Sidebar, Header)
│   │   │   └── FileTree.tsx      # Component for the folder view tree
│   │   ├── hooks/
│   │   │   └── useDriveData.ts   # Custom hooks for fetching data
│   │   ├── types/
│   │   │   └── index.ts          # TypeScript type definitions
│   │   ├── views/                # Top-level page components
│   │   │   ├── FolderView.tsx
│   │   │   └── UserView.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
└── .gitignore
```

---

## **Architectural Plan** 🏛️

The system is designed as a **single-page application (SPA)** with a decoupled backend.

1.  **Authentication**: The backend handles the **Google OAuth 2.0** flow, securely managing user tokens to authorize API calls to Google Drive.
2.  **API Communication**: The React frontend makes asynchronous API calls to the FastAPI backend to fetch data or trigger actions (e.g., `GET /api/v1/files/{folderId}`). It does not interact directly with the Google Drive API.
3.  **Backend Logic**: The backend serves as a secure proxy. It receives requests from the frontend, uses the stored user tokens to interact with the Google Drive API, processes the data, and returns it to the client in a clean, predictable JSON format.
4.  **Frontend Rendering**: The React app receives the JSON data and uses it to render the UI. The application state is managed within React to create a responsive experience as the user navigates through different views.

---

## **Development Roadmap** 🗺️

The project will be built in three phases:

1.  **Backend Foundation**: Implement the FastAPI server, Google OAuth 2.0 authentication, and core services for interacting with the Google Drive API.
2.  **Frontend Scaffolding**: Set up the React/Vite project, including the main layout, routing, and the `axios` API layer for backend communication.
3.  **Feature Implementation**: Build the two main UI views sequentially:
    * **Folder View**: Develop the file tree and the master-detail layout to display permissions for selected items.
    * **User View**: Create the user list and the logic to display all items a specific user can access, along with permission management controls.