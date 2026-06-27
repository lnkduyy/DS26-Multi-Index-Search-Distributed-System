# Distributed Food Search System

A highly scalable, microservices-based distributed system that allows users to search for food recipes using natural language. The system leverages a custom Raft-based consensus orchestrator, Google's Gemini LLM for intent decomposition, and Qdrant Vector Database for semantic search.

## 🏗 System Architecture

The project is structured into three main interoperable microservices (nodes) and one shared library.

```mermaid
graph TD
    Client((Client)) -->|POST /search| Coordinator(Coordinator Node<br/>Port: 8080)
    Coordinator -->|Raft Consensus| Coordinator2(Coordinator Follower<br/>Port: 8081)
    
    Coordinator -->|1. Parse Intent| LLM_Decompose(LLM Node<br/>Port: 8120)
    LLM_Decompose -->|Pass-through| Python_FastAPI(Python FastAPI<br/>Port: 5000)
    Python_FastAPI -.->|Gemini API| Gemini((Gemini 2.5 Flash))
    
    Coordinator -->|2. Search DB| Recipe(Recipe Node<br/>Port: 8082)
    Recipe -.->|gRPC| Qdrant[(Qdrant Vector DB<br/>Port: 6334)]
    
    Coordinator -->|3. Generate Answer| LLM_Answer(LLM Node<br/>Port: 8120)
    LLM_Answer --> Python_FastAPI
```

### Modules Overview

1. **`coordinator`**: The master orchestrator. Implements the Raft Consensus algorithm for high availability. It manages the state machine of incoming requests and delegates work sequentially to the other nodes.
2. **`llm-node`**: An AI Gateway consisting of a Spring Boot proxy and a Python/FastAPI backend. It uses LangChain and Gemini to decompose messy natural language into structured JSON filters, and later formats the search results into a conversational answer.
3. **`recipe-node`**: The search engine. It connects to a Qdrant Vector Database via gRPC. It applies both semantic vector search (using `sentence-transformers`) and metadata filtering to find the best recipes matching the decomposed criteria.
4. **`shared-models`**: A common Java library containing data transfer objects (DTOs) like `RecipeQuery` and `SearchResponse` used across all Spring Boot nodes.

---

## 🚀 Getting Started

### Prerequisites
- Java 17+ and Maven 3.8+
- Python 3.10+
- Docker & Docker Compose (for Qdrant)

### Environment Setup

Create a `.env` file at the root of `llm-node/python-llm-api/` with your API key:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

### Running the System

The entire ecosystem is orchestrated using **Docker Compose**.

```bash
# Start all microservices, databases, and the Nginx proxy
docker-compose up -d --build
```

This single command will:
1. Spin up the Qdrant Vector Database
2. Spin up the Nginx Reverse Proxy
3. Spin up the Frontend Vite App
4. Spin up the Coordinator (Java)
5. Spin up the Recipe Node (Java)
6. Spin up the LLM Node Proxy (Java)
7. Spin up the Python LLM API
8. Spin up the Python ETL API

Once running, you can access the frontend web application at `http://epicure.localhost`. All nodes are automatically wired up together via the `cluster-init` service.

---

## 🛠 API Usage

Send a natural language search request to the Coordinator:

```bash
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{
    "userQuery": "I need a high protein dinner that takes less than 30 minutes to cook"
  }'
```

Returns a Tracking ID. Poll the result using:
```bash
curl -X GET "http://localhost:8080/get?id=<YOUR_TRACKING_ID>"
```
