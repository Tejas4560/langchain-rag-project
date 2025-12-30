# Dockerized LangChain RAG Application

This application is containerized using Docker and Docker Compose.

## Services

- **Backend**: FastAPI application running on port 8000
- **Frontend**: React application served by Nginx on port 3000

## Prerequisites

- Docker
- Docker Compose

## Setup and Run

1. Ensure you have a `.env` file in the root directory with necessary environment variables (e.g., API keys).

2. Build and start the services:

   ```bash
   docker-compose up --build
   ```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Volumes

- `./data` is mounted to `/app/data` in the backend container for file uploads.
- `./vectorstore` is mounted to `/app/vectorstore` in the backend container for the FAISS vector database.
- `./.env` is mounted to `/app/.env` in the backend container for environment variables.

## Development

For development, you can run the containers in detached mode:

```bash
docker-compose up -d
```

To stop the services:

```bash
docker-compose down
```

To rebuild after code changes:

```bash
docker-compose up --build
```