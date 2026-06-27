# LLM Node

`llm-node` is a hybrid microservice (Spring Boot + Python/FastAPI) that acts as the intelligence layer of the distributed food search system. It utilizes LangChain and Google's **Gemini 3.1 Flash Lite / 2.5 Flash** models to parse natural language user queries and generate friendly food recommendations.

## 🧩 Data Flow Architecture

This module is split into two interoperable layers:
1. **Java Proxy (`llm-node`)**: An API Gateway that receives requests from the Coordinator and proxies them to the Python backend without the overhead of heavy JSON parsing.
2. **Python Backend (`python-llm-api`)**: A FastAPI service that manages the LangChain pipelines, prompts, and interacts directly with the Google Gemini API.

```text
POST /llm/decompose
POST /llm/answer
         |
    LLMController (Java Proxy)
         |
     LLMService (Java)
         | (HTTP Pass-through)
  app.py (FastAPI Python)
         |
   llm.py (LangChain & Gemini)
```

---

## 🌟 Key Features

1. **Intent Decomposition**:
   - Parses messy user queries (e.g., "I want a high protein chicken dinner under 30 mins") into a strict, structured JSON payload that the Recipe Node can use for vector search.
2. **Conversational Answer Generation**:
   - Takes the structured recipes returned by the Recipe Node and uses Gemini to write a natural, conversational response back to the user.

---

## 🚀 How to Run

This node is automatically managed by Docker Compose. You do not need to start it manually.

```bash
cd ..
docker-compose up -d --build llm-node-1 llm-node-2 python-llm-api
```

*(By default, the Java nodes run internally on ports 8120/8121, and the Python API runs on port 5000).*
