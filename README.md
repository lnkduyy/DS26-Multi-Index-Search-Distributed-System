# Epicure — Distributed Multi-Index Search & Data Pipeline Platform

[![Java](https://img.shields.io/badge/Java-17%2B-orange.svg)](https://www.oracle.com/java/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.x-green.svg)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-red.svg)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Nginx](https://img.shields.io/badge/Nginx-L7%20Proxy-009639.svg)](https://nginx.org/)
[![Paper](https://img.shields.io/badge/Paper-IEEE%20Format-red.svg)](docs/Epicure_Research_Paper.pdf)

> 📄 **Academic Research Paper**: Read our full 13-page IEEE-format conference paper: [Epicure_Research_Paper.pdf](docs/Epicure_Research_Paper.pdf)

**Epicure** is an enterprise-grade, distributed microservices platform designed for high-throughput semantic query processing, automated data ETL pipelines, and multi-factor ranking. Built with resilience, scalability, and high availability at its core, the entire system is orchestrated via Docker Compose and balanced through a Layer 7 reverse proxy.

---

## 🏗️ System Architecture

```text
                                 [ Client / Frontend (React + Vite) ]
                                                  │
                                                  ▼
                                       [ Nginx Layer 7 Gateway ]
                                      (Round-Robin Load Balancer)
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    ▼                             ▼                             ▼
         [ Coordinator Node 1 ]        [ Coordinator Node 2 ]        [ Coordinator Node 3 ]
         (Port: 8080 - Leader)         (Port: 8081 - Replica)        (Port: 8082 - Replica)
                    └─────────────────────────────┬─────────────────────────────┘
                                                  │
            ┌─────────────────────────────────────┼─────────────────────────────────────┐
            ▼                                     ▼                                     ▼
   [ Recipe Clustered Nodes ]           [ ETL Processing Pipeline ]           [ LLM Reasoning Nodes ]
   (3 Nodes: 8100, 8101, 8102)          (2 Nodes: 8140, 8141)                 (2 Nodes: 8120, 8121)
            │                                     │                                     │
            ▼                                     ▼                                     ▼
   [ Qdrant Vector Database ]           [ SentenceTransformers Engine ]       [ Google Gemini LLM API ]
   (Dense Vector Embeddings)            (Feature Extraction & Vectorization)  (Semantic Query Synthesis)
```

---

## ⚙️ Core Engineering Highlights

### 1. Distributed Consensus & Leader Election
* Orchestrated a 3-node **Coordinator Cluster** utilizing an internal Raft-inspired consensus protocol to designate cluster leaders, manage task dispatching, and synchronize global state.
* Built-in health check and fault detection ensures that any failing coordinator is seamlessly isolated without interrupting incoming client requests (tested with ~5.15s automated failover and zero request loss).

### 2. High-Throughput Data Pipeline (ETL)
* Implemented dedicated **ETL Nodes** powered by Python FastAPI and `SentenceTransformers`.
* Automatically extracts and normalizes unstructured recipe attributes, converts textual representations into dense vector embeddings, and calculates nutritional data profiles before indexing into the vector store.

### 3. Sub-Second Semantic Vector Search (RAG)
* Integrated with **Qdrant Vector Database** to perform high-dimensional approximate nearest neighbor (ANN) searches.
* Combines semantic cosine similarity with a custom multi-factor ranking algorithm (balancing protein ratio, estimated prep time, and dietary constraints), achieving an average **Precision@5 of 0.85** (+112.5% over lexical baseline).

### 4. Layer 7 Reverse Proxy & Load Balancing
* An **Nginx** reverse proxy front-faces all external traffic, terminating client connections and distributing workloads evenly across the coordinator cluster via round-robin balancing (tested up to 1,000 concurrent requests).

### 5. Fault Tolerance & Self-Healing
* Resilient communication pattern across microservices: automated exponential backoff retries and fail-safe fallbacks prevent transient upstream API latency from causing cascading failures.

---

## 📂 Project Structure

```text
├── coordinator/           # Distributed Coordinator Service (Java 17, Spring Boot)
├── recipe-node/           # Hybrid Vector Search & Scoring Service (Spring Boot + Qdrant)
├── llm-node/              # LLM Decomposition & Synthesis (FastAPI + Spring Boot proxy)
├── ETL-node/              # Data Pipeline & Vectorization (FastAPI + SentenceTransformers)
├── frontend/              # Web Client (React 18, Vite, TypeScript)
├── nginx/                 # Layer 7 Reverse Proxy & Load Balancer Configuration
├── shared-models/         # Shared Data Models & DTOs for Java Microservices
├── docs/                  # Academic Research Paper (PDF) & Documentation
├── scripts/               # Automation & Deployment Scripts (Windows / Linux)
├── docker-compose.yml     # Multi-Container Cluster Orchestration
├── pom.xml                # Maven Root Parent Project
└── .env.example           # Environment Variables Template
```

---

## 🛠️ Microservices Overview

| Microservice | Technology Stack | Ports | Description |
| :--- | :--- | :--- | :--- |
| **`gateway`** | Nginx | `80`, `443` | Layer 7 Reverse Proxy & Load Balancer |
| **`coordinator`** | Java 17, Spring Boot | `8080`, `8081`, `8082` | Cluster coordinator, leader election, and state synchronization |
| **`recipe-node`** | Java 17, Spring Boot | `8100`, `8101`, `8102` | Vector DB search execution and multi-attribute ranking engine |
| **`ETL-node`** | Python 3.11, FastAPI, PyTorch | `8140`, `8141` | Ingredient extraction, nutrition calculation, and vectorization |
| **`llm-node`** | Python 3.11, FastAPI, Gemini API | `8120`, `8121` | Natural language processing, prompt engineering, query synthesis |
| **`qdrant`** | Rust (Qdrant Core) | `6333`, `6334` | High-dimensional vector database for dense embeddings |
| **`frontend`** | React 18, Vite, TypeScript | `5173` | Responsive web client for end-user interaction |

---

## 🚀 Quickstart & Deployment

### 1. Prerequisites
* **Docker & Docker Compose** (v2.20+)
* API Keys for Google Gemini and Qdrant Cloud (or use local Qdrant container)

### 2. Configuration
Copy and configure the environment variables:
```bash
cp .env.example .env
```
Fill in your credentials in `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
QDRANT_API_KEY=your_qdrant_api_key_here
```

### 3. Launching the Cluster
* **Via Automated Script (Windows):**
  ```cmd
  .\scripts\start-system.bat
  ```
* **Via Docker Compose:**
  ```bash
  docker compose up -d --build
  ```

### 4. Verification
* Access the Web Application at: `http://epicure.localhost`
* Cluster Health & Metrics: `http://epicure.localhost/api/cluster/status`

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
