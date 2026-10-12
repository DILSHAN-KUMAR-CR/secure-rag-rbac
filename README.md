<div align="center">

# Secure RAG with Role-Based Access Control

### A permission-aware document retrieval and question-answering API

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Permissions-003B57?logo=sqlite&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20Search-DC244C?logo=qdrant&logoColor=white)

**Authenticate · Filter permitted documents · Retrieve relevant chunks · Recheck permissions**

</div>

---

## Overview

Secure RAG with Role-Based Access Control (RBAC) is a document retrieval application designed to prevent users from retrieving documents that their role is not allowed to access.

The application uses **FastAPI** for its API, **SQLite** as the source of truth for users and document permissions, and **Qdrant** for local vector search. It supports keyword retrieval, semantic retrieval, and hybrid retrieval techniques. Access permissions are applied during retrieval so that relevant but unauthorized documents are not returned to the user.

The project uses fictional policy documents to demonstrate role-based access, including an HR-only salary policy.

## Features

- User authentication and role-based authorization.
- Admin-managed users and document permissions.
- PDF and text document ingestion, chunking, and indexing.
- Keyword-based document retrieval.
- Semantic retrieval using local vector search.
- Hybrid retrieval that combines keyword and semantic rankings with Reciprocal Rank Fusion (RRF).
- Permission checks against the user's role and allowed document IDs.
- RAG context preparation with authorization rechecks.
- Retrieval evaluation using Precision@K, Recall@K, and Mean Reciprocal Rank (MRR@K).
- Automated tests for application behavior and access control.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| FastAPI | REST API and interactive API documentation |
| SQLite | Users, documents, chunks, and role permissions |
| Qdrant local mode | Vector storage and semantic retrieval |
| FastEmbed / embeddings | Text embeddings for semantic search |
| Pytest | Automated tests |
| Git and GitHub | Version control and repository hosting |

## How RBAC Works

1. A user authenticates and makes a request.
2. The application identifies the user's current role.
3. The application determines which document IDs the role can access.
4. Retrieval searches only permitted content.
5. The application rechecks canonical document data and permissions before preparing RAG context.

### Example access policy

| Document | Employee | HR | Admin |
|---|---:|---:|---:|
| Company Leave Policy | Allowed | Allowed | Depends on configured document permissions |
| Remote Work Policy | Allowed | Allowed | Depends on configured document permissions |
| Salary Administration Policy | Blocked | Allowed | Depends on configured document permissions |

**Note:** Document access is controlled by each document's configured permissions. Admin management privileges do not automatically grant access to every document during retrieval.

## Project Structure

```text
secure-rag-rbac/
├── app/
│   ├── main.py
│   ├── rag_service.py
│   ├── retrieval_service.py
│   ├── vector_service.py
│   ├── hybrid_retrieval_service.py
│   ├── evaluate_retrieval.py
│   └── inspect_chunks.py
├── data/
│   ├── secure_rag.db       # Created locally; do not commit
│   └── vector_store/       # Created locally; do not commit
├── evaluation/
│   └── retrieval_cases.json
├── tests/
├── screenshots/
├── .gitignore
├── README.md
└── requirements.txt
```

Your local project may contain additional modules or folders.

## Requirements

- Python 3
- Git
- Windows PowerShell or another terminal
- Dependencies listed in `requirements.txt`

## Installation and Setup

### 1. Clone your GitHub repository

Replace `YOUR_GITHUB_USERNAME` with your GitHub username after creating the repository.

```powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/secure-rag-rbac.git
cd secure-rag-rbac
```

If you already have the project locally, you can skip cloning and open PowerShell in the project folder.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 5. Open the API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/health

## Sample Documents Used

The local demonstration includes these fictional documents:

- **Company Leave Policy** — accessible to Employee and HR.
- **Remote Work Policy** — accessible to Employee and HR.
- **Salary Administration Policy** — accessible to HR only.

Upload documents through the Admin document endpoint and reindex them when required.

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /auth/login` | Authenticate a user |
| `GET /auth/me` | Inspect the authenticated account, if enabled in the current version |
| `GET /admin/users` | List users as an Admin |
| `POST /admin/users` | Create a user as an Admin |
| `GET /admin/documents` | List documents and configured permissions |
| `POST /admin/documents` | Upload a document |
| `PATCH /admin/documents/{document_id}/permissions` | Update document access |
| `POST /admin/documents/reindex` | Rebuild the vector index |
| `POST /retrieval/search` | Search permitted chunks by keyword |
| `POST /retrieval/semantic-search` | Search permitted chunks semantically |
| `POST /rag/context-preview` | Preview authorized context, if enabled |
| `POST /rag/ask` | Ask a question using retrieved context, if enabled |
| `GET /health` | Check API health |

The exact routes available are those shown in the running application's Swagger UI at `/docs`.

## Testing

Run the automated test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run the retrieval evaluation with the API server stopped, to avoid opening the local Qdrant storage from multiple processes:

```powershell
.\.venv\Scripts\python.exe -m app.evaluate_retrieval
```

The evaluation compares keyword, semantic, and hybrid retrieval using Precision@K, Recall@K, and MRR@K. Evaluation results depend on the cases and documents configured in your local environment.

## Screenshots

Add your own screenshots to the `screenshots/` folder in the repository. Capture screenshots from your running application; do not include passwords, bearer tokens, API keys, or other private information.

Suggested screenshots:

1. `swagger-docs.png` — the FastAPI Swagger page.
2. `documents-list.png` — the Admin document list showing configured roles.
3. `hr-salary-search.png` — HR retrieving the Salary Administration Policy.
4. `employee-search.png` — Employee search results that do **not** include the HR-only salary document.

After adding the image files, uncomment and update the image links below to match the filenames you actually saved:

<!--
### Swagger API

![Swagger API](screenshots/swagger-docs.png)

### Document permissions

![Document permissions](screenshots/documents-list.png)

### HR retrieval

![HR retrieving salary policy](screenshots/hr-salary-search.png)

### Employee access restriction

![Employee search excluding HR-only document](screenshots/employee-search.png)
-->

## Security Notes

- Do not commit `.env` files, passwords, access tokens, local databases, uploaded private documents, or vector-store data.
- Use fictional or approved documents during demonstrations.
- Check `.gitignore` before pushing the repository to GitHub.
- This project is a demonstration and should receive a security review before use with confidential or production data.

## Author

**Dilshan Kumar**

- GitHub: `https://github.com/YOUR_GITHUB_USERNAME`
- Repository: `https://github.com/YOUR_GITHUB_USERNAME/secure-rag-rbac`

Replace `YOUR_GITHUB_USERNAME` in the links and installation command after creating your repository.

---

<div align="center">

Built as a demonstration of permission-aware document retrieval and role-based access control.

</div>
