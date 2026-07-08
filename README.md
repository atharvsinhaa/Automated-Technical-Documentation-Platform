![Python](https://img.shields.io/badge/Python-3.11-blue)

![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)

![Angular](https://img.shields.io/badge/Angular-Frontend-red)

![Neo4j](https://img.shields.io/badge/Neo4j-GraphDB-blue)

![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-orange)

![Docker](https://img.shields.io/badge/Docker-Containerized-blue)

![License](https://img.shields.io/badge/License-Apache%202.0-green)


# 🚀 Enterprise AI Documentation Platform

> AI-powered repository analysis platform that automatically generates Enterprise-Level High Level Design (HLD), Low Level Design (LLD), Architecture Diagrams, Code Documentation, and Knowledge Graphs from any source code repository.

---

## 📌 Overview

Modern enterprise repositories often lack accurate documentation, making onboarding, maintenance, and architecture understanding extremely difficult.

This platform automates the entire documentation workflow using AI, static code analysis, knowledge graphs, and local LLM inference.

Instead of spending days manually understanding a codebase, developers can generate complete technical documentation within minutes.

---

## ✨ Features

### 📂 Repository Analysis

- Upload local repositories
- Import GitHub repositories
- Paste source code directly
- Automatic language detection

---

### 🧠 AI Documentation Generation

- High Level Design (HLD)
- Low Level Design (LLD)
- Inline Code Documentation
- Architecture Summary
- Repository Profile

---

### 🏗 Architecture Intelligence

- Component Detection
- Dependency Mapping
- Service Relationships
- Module Hierarchy
- Data Flow Analysis

---

### 📊 Business Intelligence Dashboard

- Repository Insights
- Complexity Metrics
- Code Statistics
- Technology Detection
- Repository Health

---

### 🕸 Knowledge Graph

- Neo4j Integration
- Entity Relationships
- Graph-based Repository Search
- GraphRAG Ready Architecture

---

### 🔍 Semantic Search

- AI-powered code search
- Context-aware retrieval
- Repository understanding
- Natural language querying

---

### 🎨 Enterprise UI

- Angular Frontend
- Responsive Design
- Dark & Light Theme
- Interactive Dashboard
- Modern Enterprise Layout

---

## 🏛 System Architecture

```
                    ┌──────────────────────┐
                    │   Angular Frontend   │
                    └──────────┬───────────┘
                               │
                         REST API
                               │
                    ┌──────────▼───────────┐
                    │     FastAPI API      │
                    └──────────┬───────────┘
                               │
        ┌──────────────┬────────┼──────────────┐
        │              │        │              │
 AST Parser      Knowledge Graph   AI Pipeline
        │              │        │
        ▼              ▼        ▼
 Repository IR      Neo4j     Ollama LLM
        │              │        │
        └──────────────┼────────┘
                       ▼
             Documentation Engine
                       │
                       ▼
       HLD • LLD • Diagrams • Comments
```

---

## ⚙ Tech Stack

### Frontend

- Angular
- TypeScript
- HTML5
- CSS3

### Backend

- FastAPI
- Python
- REST APIs

### AI & Documentation

- Ollama
- AST Parsing
- GraphRAG
- Mermaid
- Markdown Generation

### Database

- Neo4j

### DevOps

- Docker
- Docker Compose
- Nginx

---

## 📁 Project Structure

```
Enterprise-AI-Documentation/

│
├── frontend-angular-ui/
│     ├── src/
│     ├── assets/
│     └── ...
│
├── ai-doc-system/
│     ├── backend/
│     ├── pipeline/
│     ├── generators/
│     ├── parsers/
│     ├── graph/
│     └── ...
│
├── docker-compose.yml
└── README.md
```

---

## 🚀 Getting Started

### Clone Repository

```bash
git clone https://github.com/yourusername/repository-name.git

cd repository-name
```

### Docker

```bash
docker compose up --build
```

### Backend

```bash
cd ai-doc-system

pip install -r requirements.txt

uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend-angular-ui

npm install

ng serve
```

---

## 📸 Platform Modules

- 🏠 Dashboard
- 📄 AI Documentation
- 📈 Business Intelligence
- 🕸 Graph Intelligence
- 🔍 Semantic Search
- 📜 Audit Logs
- ⚙ Settings

---

## 🎯 Generated Outputs

✔ High Level Design

✔ Low Level Design

✔ Mermaid Architecture Diagrams

✔ Repository Summary

✔ Component Analysis

✔ Dependency Mapping

✔ Inline Code Comments

✔ Knowledge Graph

---

## 💡 Future Enhancements

- Multi Repository Analysis
- Jira Integration
- Confluence Export
- PDF & DOCX Export
- Architecture Version Comparison
- CI/CD Integration
- Multi-LLM Support
- Enterprise Authentication

---

## 📜 License

Licensed under the Apache License 2.0.

---

## 👨‍💻 Author

**Atharv Sinha**

Computer Science (AI & ML)

Enterprise AI | Backend Engineering | Generative AI | Full Stack Development

---

⭐ If you found this project interesting, consider giving it a Star!
