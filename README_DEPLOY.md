# Deployment Guide

This project is fully containerized and ready to be deployed to any Docker host or Platform-as-a-Service (PaaS) such as Render, Railway, or Fly.io.

## Local Development via Docker Compose

To run the entire stack locally using Docker Compose:

1. Clone the repository.
2. Inside the `ai-doc-system/` directory, copy `.env.example` to `.env` if it doesn't already exist.
3. From the repository root (where `docker-compose.yml` is located), run:

```bash
docker-compose up --build
```

This will build the images and bring up the **backend** (FastAPI), **frontend** (Angular + Nginx), and a local instance of **Ollama**.
The Angular dashboard will be available at [http://localhost:4200](http://localhost:4200).

## Committed LLM Path: Ollama

A local, self-hosted **Ollama** instance is the committed and fully integrated LLM path for this enterprise documentation system. By ensuring all LLM operations run completely locally via Ollama, we guarantee that proprietary source code and architecture details never leave your infrastructure.

Currently, the stack includes Ollama directly in the `docker-compose.yml` for convenience and persistence (using a Docker volume). Because `OLLAMA_HOST` is designed to be fully configurable via environment variables (see `ai-doc-system/.env`), migrating to a dedicated in-house GPU server or cluster in the future is as simple as updating the `OLLAMA_HOST` URL to point to that server. Absolutely no code changes are required.
