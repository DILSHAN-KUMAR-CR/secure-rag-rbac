# Secure RAG with Role-Based Access Control (RBAC)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python badge" />
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI badge" />
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite&logoColor=white" alt="SQLite badge" />
  <img src="https://img.shields.io/badge/Qdrant-Vector%20Store-DC244C" alt="Qdrant badge" />
  <img src="https://img.shields.io/badge/Pytest-Testing-0A9EDC?logo=pytest&logoColor=white" alt="Pytest badge" />
</p>

<p align="center">
  <a href="https://github.com/DILSHAN-KUMAR-CR/secure-rag-rbac">
    <img src="https://img.shields.io/badge/GitHub-Repository-181717?logo=github&logoColor=white" alt="GitHub repository badge" />
  </a>
  <img src="https://img.shields.io/badge/Access%20Control-RBAC-orange" alt="RBAC badge" />
</p>

A secure Retrieval-Augmented Generation (RAG) application that applies role-based access control to document retrieval. Built with FastAPI, SQLite, and a local Qdrant vector store.

## Overview

This project demonstrates how to retrieve relevant documents while respecting user roles and document permissions. Access checks are applied so users can retrieve only documents their role is authorized to access.

## Features

- **Role-based access control (RBAC)** for document retrieval
- **Document management** and indexing
- **Semantic and keyword-based retrieval**
- **Hybrid retrieval support**
- **FastAPI REST API** with interactive Swagger documentation
- **SQLite** for application data
- **Qdrant** for local vector storage
- **Automated tests** for core functionality

## Technology Stack

- **Backend:** Python, FastAPI
- **Database:** SQLite
- **Vector store:** Qdrant (local storage)
- **API documentation:** Swagger UI / OpenAPI
- **Testing:** Pytest

## Role-Based Access Control

Documents are associated with permitted roles. A user can retrieve a document only when their role is authorized by that document's access policy.

Example policy configured in the project:

| Document | Permitted roles |
|---|---|
| Company Leave Policy | Employee, HR |
| Remote Work Policy | Employee, HR |
| Salary Administration Policy | HR |

The examples above describe the project's configured document permissions. Actual access depends on the authenticated user's role and the API's authorization checks.

## Project Structure

```text
secure-rag-rbac-main/
├── app/
├── data/
│   ├── secure_rag.db
│   └── vector_store/
├── tests/
├── .venv/
├── README.md
└── ...
```

*Note: The exact files and folders may vary depending on the repository version. Keep the local database and vector-store data if you want to preserve your indexed documents.*

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/DILSHAN-KUMAR-CR/secure-rag-rbac.git
cd secure-rag-rbac
```

### 2. Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, you can use the environment's Python executable directly instead.

### 3. Install dependencies

If the repository contains `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

If dependencies are managed through another project file, follow that file's installation instructions.

### 4. Start the API

From the project root, run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

If the virtual environment is activated, this may also work:

```bash
uvicorn app.main:app --reload
```

### 5. Open the API documentation

- **Swagger UI:** http://127.0.0.1:8000/docs
- **Health endpoint:** http://127.0.0.1:8000/health

Use Swagger UI to inspect the available endpoints and send API requests.

## API Endpoints

The application exposes API routes for health checks, authentication/user management, document operations, retrieval, and RAG queries. Exact paths and request schemas depend on the current application implementation.

Open `http://127.0.0.1:8000/docs` to view the authoritative list of endpoints and their required inputs.

## Testing

Run the project's test suite from the repository root. For example, if Pytest is installed:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

A previous run of this project's tests reported **83 passed and 1 warning**. Run the tests again on your current checkout to confirm the current result.

## Security Notes

- Document access should be enforced by the backend, not only by the user interface.
- Keep secrets and credentials out of source control.
- Do not commit local environment files containing passwords, API keys, or other secrets.
- Preserve `data/secure_rag.db` and `data/vector_store/` if you need to retain local application data.
- Test each role with both permitted and restricted documents when validating authorization.

## Author

**Dilshan Kumar**

- **GitHub:** https://github.com/DILSHAN-KUMAR-CR
- **Repository:** https://github.com/DILSHAN-KUMAR-CR/secure-rag-rbac
