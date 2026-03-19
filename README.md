# ScholarGraph

![CI](https://github.com/aamirk24/WebServices/actions/workflows/ci.yml/badge.svg)

> A FastAPI-based research paper discovery and analytics platform featuring semantic search, citation graph analysis, author impact summaries, authenticated annotations, API keys, background crawling, and MCP integration.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture Diagram](#architecture-diagram)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Endpoints Reference](#api-endpoints-reference)
- [Example Requests](#example-requests)
- [MCP Server Setup](#mcp-server-setup)
- [Running Tests](#running-tests)
- [Deployment Notes](#deployment-notes)
- [Tech Stack with Justifications](#tech-stack-with-justifications)
- [Suggested Demo Flow](#suggested-demo-flow)
- [Author](#author)

---

## Project Overview

**ScholarGraph** is a backend API for exploring a corpus of academic research papers in a more intelligent and research-friendly way than simple keyword search. It combines traditional paper metadata retrieval, semantic search using vector embeddings, citation-graph analytics using PageRank, author impact summaries, user-authenticated annotations, API-key based tooling access, and MCP server integration for AI-assisted workflows.

The system ingests and enriches research data from **arXiv** and **Semantic Scholar**. arXiv provides the paper corpus and metadata, while Semantic Scholar is used as a key citation source for building and enriching the citation graph. This allows ScholarGraph to move beyond “paper storage” into actual research discovery: users can browse papers, inspect citation structure, retrieve authors, annotate interesting papers, trigger corpus maintenance jobs, and expose high-value research actions to LLM clients through MCP.

### Core capabilities

#### Paper Discovery
- List papers with pagination
- Filter papers by category
- Retrieve full paper metadata
- View authors for a paper
- View citations and references for a paper
- Run semantic search over paper abstracts
- Find papers similar to an existing paper

#### Research Analytics
- Rank papers by **PageRank** over the citation graph
- Analyse topic/category statistics
- View publication trends over time
- Summarise author impact and top papers

#### User Functionality
- User registration and JWT login
- Access token refresh
- API key generation and revocation
- Paper annotations with owner-controlled editing/deletion

#### Corpus Maintenance
- Crawl topic-specific papers
- Seed foundational missing papers
- Build citation graph edges for one topic or the full corpus
- Trigger background embedding generation
- Trigger background PageRank recomputation

#### AI / Tool Integration
- MCP server support
- API-key based external tool access
- Natural-language paper discovery workflows for desktop AI clients

---

## Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENTS                                     │
│─────────────────────────────────────────────────────────────────────────────│
│ Browser / Swagger UI / curl / Postman / Python scripts / MCP host / Claude │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP / JSON
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI APP                                   │
│─────────────────────────────────────────────────────────────────────────────│
│ app.main                                                                    │
│ routers/                                                                    │
│   • auth                                                                    │
│   • papers                                                                  │
│   • authors                                                                 │
│   • annotations                                                             │
│   • analytics                                                               │
│   • crawl                                                                   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
┌────────────────────────────┐      ┌────────────────────────────────────────┐
│         CRUD LAYER         │      │             SERVICE LAYER              │
│────────────────────────────│      │────────────────────────────────────────│
│ SQLAlchemy async queries   │      │ auth / JWT / API keys                  │
│ papers / authors / cites   │      │ embeddings / semantic search           │
│ users / annotations        │      │ pagerank / crawler / background jobs   │
└───────────────┬────────────┘      └──────────────────────┬─────────────────┘
                │                                          │
                └───────────────────┬──────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          POSTGRESQL + PGVECTOR                              │
│─────────────────────────────────────────────────────────────────────────────│
│ papers / authors / paper_authors / citations / users / api_keys             │
│ annotations / abstract_embedding vectors                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL RESEARCH SOURCES                             │
│─────────────────────────────────────────────────────────────────────────────│
│ arXiv API / Semantic Scholar API / background corpus enrichment             │
└─────────────────────────────────────────────────────────────────────────────┘


Optional AI Layer
──────────────────────────────────────────────────────────────────────────────
mcp_server/server.py runs as a separate stdio process and calls the FastAPI
API over HTTP using a ScholarGraph API key.
```

---

## Quick Start

### Prerequisites

Before starting, make sure you have:

- **Python 3.12+**
- **PostgreSQL**
- **pgvector** available in PostgreSQL
- **uv** installed

### Get running from scratch in 5 commands

```bash
git clone https://github.com/aamirk24/WebServices.git && cd WebServices
cp .env.example .env
psql postgres -c "CREATE USER sguser WITH PASSWORD 'yourpassword';"
psql postgres -c "CREATE DATABASE scholargraph OWNER sguser;" && psql scholargraph -c "CREATE EXTENSION IF NOT EXISTS vector;"
uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```

### After startup

- **API Base URL:** `http://127.0.0.1:8000`
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **OpenAPI JSON:** `http://127.0.0.1:8000/openapi.json`

### Notes

- After copying `.env.example`, update values such as `DATABASE_URL`, `SECRET_KEY`, and any admin-email settings to match your local setup.
- The database URL should use the user you created above, for example:

```env
DATABASE_URL=postgresql+asyncpg://sguser:yourpassword@localhost:5432/scholargraph
```

---

## Environment Variables

Create a `.env` file in the project root.

### Minimal local `.env`

```env
DATABASE_URL=postgresql+asyncpg://sguser:yourpassword@localhost:5432/scholargraph
SECRET_KEY=replace_this_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENVIRONMENT=development
```

### Production / deployment notes

In production, you will typically also set:

```env
ALLOWED_ORIGINS=["https://your-deployed-site.onrender.com"]
CRAWL_ADMIN_EMAILS=your-email@example.com
```

### Environment Variables Table

| Variable | Required | Purpose |
|---|---:|---|
| `DATABASE_URL` | Yes | Async PostgreSQL connection string using `postgresql+asyncpg://...` |
| `SECRET_KEY` | Yes | JWT signing secret |
| `ALGORITHM` | Yes | JWT algorithm, typically `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Access token lifespan |
| `ENVIRONMENT` | Recommended | `development` or `production` |
| `ALLOWED_ORIGINS` | Production | JSON list of allowed CORS origins |
| `CRAWL_ADMIN_EMAILS` | Recommended | Comma-separated admin emails for privileged maintenance endpoints |
| `SCHOLARGRAPH_API_KEY` | MCP only | API key used by the MCP server |

---

## API Endpoints Reference

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Register a new user account |
| POST | `/auth/login` | No | Log in and receive access + refresh tokens |
| POST | `/auth/refresh` | No | Refresh an access token using a refresh token |
| GET | `/auth/me` | Yes | Return the currently authenticated user |
| POST | `/auth/api-keys` | Yes | Create a new API key |
| GET | `/auth/api-keys` | Yes | List API keys belonging to the authenticated user |
| DELETE | `/auth/api-keys/{api_key_id}` | Yes | Revoke one API key |

### Papers

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/papers` | No | List papers with pagination and optional category / search filters |
| GET | `/papers/ranked` | No | Return top papers ranked by PageRank |
| GET | `/papers/search/semantic` | No | Run semantic search over abstract embeddings |
| GET | `/papers/{paper_id}` | No | Return one paper by internal UUID |
| GET | `/papers/{paper_id}/similar` | No | Return papers semantically similar to the source paper |
| GET | `/papers/{paper_id}/citations` | No | Return citation relationships for a paper |
| GET | `/papers/{paper_id}/authors` | No | Return authors associated with a paper |

### Authors

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/authors` | No | List authors with aggregate metrics |
| GET | `/authors/{author_id}` | No | Return one author and their associated papers |
| GET | `/authors/{author_id}/impact` | No | Return author impact analytics |

### Annotations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/papers/{paper_id}/annotations` | Yes | Create an annotation on a paper |
| GET | `/papers/{paper_id}/annotations` | No | List annotations for a paper |
| PUT | `/annotations/{annotation_id}` | Yes (owner) | Update an annotation |
| DELETE | `/annotations/{annotation_id}` | Yes (owner) | Delete an annotation |

### Analytics

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/analytics/pagerank` | Yes (admin) | Trigger background PageRank recomputation |
| GET | `/analytics/topics` | No | Return topic/category analytics |
| GET | `/analytics/trend` | No | Return publication trends over time |
| POST | `/analytics/embed-papers` | Yes (admin) | Trigger background embedding generation |

### Crawl / Corpus Maintenance

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/crawl` | Yes (admin) | Start a background crawl for an arXiv topic |
| POST | `/crawl/seed-foundations` | Yes | Seed missing foundational papers |
| POST | `/crawl/build-graph` | Yes | Build graph edges for one topic |
| POST | `/crawl/build-graph-all` | Yes | Build graph edges across the full corpus |

---

## Example Requests

### Register

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "aamir",
    "email": "aamir@example.com",
    "password": "StrongPassword123!"
  }'
```

### Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=aamir@example.com&password=StrongPassword123!"
```

### Semantic Search

```bash
curl "http://127.0.0.1:8000/papers/search/semantic?q=transformer attention mechanism&limit=5"
```

### Ranked Papers

```bash
curl "http://127.0.0.1:8000/papers/ranked?category=cs.AI&limit=10"
```

### Trigger PageRank

```bash
curl -X POST http://127.0.0.1:8000/analytics/pagerank \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## MCP Server Setup

ScholarGraph supports an **MCP-compatible server layer** so AI clients can use the system as a tool-based backend rather than only through manual REST calls.

### MCP Purpose

The MCP server is intended to expose high-value research operations such as:

- semantic paper search
- retrieving top ranked papers
- looking up paper details
- finding similar papers
- summarising author impact

### 1. Create an API key

```bash
curl -X POST http://127.0.0.1:8000/auth/api-keys \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mcp-local",
    "scopes": ["papers:read", "analytics:read"]
  }'
```

> Save the raw API key immediately. It is only returned once.

### 2. Export the key locally

```bash
export SCHOLARGRAPH_API_KEY="paste_your_raw_key_here"
```

### 3. Run the MCP server

```bash
uv run python mcp_server/server.py
```

### 4. Claude Desktop example config

On macOS:

`~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "scholargraph": {
      "command": "uv",
      "args": ["run", "python", "mcp_server/server.py"],
      "env": {
        "SCHOLARGRAPH_API_KEY": "your_raw_api_key_here"
      }
    }
  }
}
```

### MCP Flow Summary

```text
Claude Desktop / AI Host
        │
        ▼
MCP Server (stdio process)
        │ HTTP + API key
        ▼
ScholarGraph FastAPI API
        │
        ▼
PostgreSQL + pgvector
```

---

## Running Tests

The project includes automated tests covering the following areas:

- **authentication flows** (`tests/test_auth.py`)
- **papers endpoints and pagination** (`tests/test_papers.py`)
- **analytics endpoints** (`tests/test_analytics.py`)
- **configuration behaviour** (`tests/test_config.py`)
- **users CRUD behaviour** (`tests/test_users_crud.py`)

### Run all tests

```bash
uv run pytest
```

### Run with coverage

```bash
uv run pytest --cov=app --cov-report=term-missing
```

### Run a single file

```bash
uv run pytest tests/test_auth.py -v
```

### CI Workflow

A GitHub Actions workflow runs tests automatically on push / pull request. The badge at the top of this README reflects the latest status.

---

## Deployment Notes

### Recommended Deployment Target

**Render** is a practical deployment target for this project.

### PostgreSQL Setup

After creating your Render PostgreSQL database, enable `pgvector`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Important Render Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>
SECRET_KEY=<your_secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENVIRONMENT=production
ALLOWED_ORIGINS=["https://scholargraph.onrender.com"]
```

### Important Deployment Notes

- `DATABASE_URL` must use **`postgresql+asyncpg://`**
- `ALLOWED_ORIGINS` should be a **JSON array string**
- if using Docker, Uvicorn should bind to **`$PORT`**
- if the app crashes before Uvicorn starts, Render may report **“No open ports detected”** even though the real issue is earlier in startup

### Typical Start Command

```bash
uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Common Deployment Problems

| Problem | Likely Cause |
|---|---|
| `No open ports detected` | App crashed before Uvicorn started |
| `No module named psycopg2` | `DATABASE_URL` used plain postgres URL instead of `+asyncpg` |
| `error parsing value for field "allowed_origins"` | `ALLOWED_ORIGINS` was not provided as valid JSON |
| CORS still open in production | Middleware still hardcoded to `"*"` instead of using config |

---

## Tech Stack with Justifications

| Technology | Why it was chosen |
|---|---|
| **FastAPI** | Excellent for async APIs, automatic Swagger/OpenAPI generation, and clean dependency injection |
| **Pydantic** | Strong validation for requests, responses, and configuration |
| **SQLAlchemy (async)** | Clean ORM/query separation and robust async database access |
| **Alembic** | Migration management for reproducible schema setup |
| **PostgreSQL** | Reliable relational database for papers, authors, citations, users, and annotations |
| **pgvector** | Enables semantic search directly inside PostgreSQL |
| **asyncpg** | Fast async PostgreSQL driver suited to the app architecture |
| **Sentence Transformers** | Provides abstract embeddings for semantic paper discovery |
| **PageRank** | Adds meaningful citation-graph influence ranking based on module graph analytics concepts |
| **arXiv API** | Provides the source corpus and paper metadata for crawling |
| **Semantic Scholar API** | Provides citation and relationship data used to enrich graph-building workflows |
| **GitHub Actions** | Automated testing and visible engineering discipline |
| **MCP** | Allows AI assistants to use ScholarGraph as a tool-based backend |
| **Render** | Straightforward deployment with managed PostgreSQL |

---

## Suggested Demo Flow

If an examiner is looking through the system for the first time, this is the strongest order to follow:

1. Open **`/docs`**
2. Register a user
3. Log in
4. Create an API key
5. Browse **`/papers`**
6. Run **semantic search**
7. Open **similar papers**
8. View **ranked papers**
9. Explore **author impact**
10. Trigger **PageRank recomputation**
11. Look at the **CI badge** in the README
12. Open **Claude Desktop** and ask: *“What are the most influential papers in cs.AI?”*  
    → Claude uses the MCP tool layer and calls the corresponding ScholarGraph tool live

This sequence demonstrates:

- authentication
- paper discovery
- semantic retrieval
- graph analytics
- author analytics
- workflow maturity
- deployment / documentation quality
- MCP-based AI integration

---

## Author

**Aamir Khan**  
University of Leeds — Computer Science
