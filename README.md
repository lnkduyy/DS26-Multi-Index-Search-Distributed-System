# Distributed Food Assistant

This is a distributed microservices project built for a university assignment. It is a smart food assistant (RAG system) that helps users search for recipes using natural language, powered by AI and vector search. 

The system is designed to be **distributed, scalable, and fault-tolerant**, running entirely on Docker Compose.

---

## 🏗️ System Architecture

The project is broken down into several independent microservices:

1. **Coordinator Nodes (`coordinator`)**: 
   - The central orchestrator (Java/Spring Boot).
   - We run 3 instances of this node. They handle leader election and manage the state of background tasks.
2. **Recipe Nodes (`recipe-node`)**: 
   - Handles searching the vector database (Qdrant) and ranking recipes based on multiple factors (protein, time, semantic match).
3. **LLM Nodes (`llm-node` / `python-llm-api`)**: 
   - Uses Google Gemini (3.1 Flash Lite) to understand user queries and generate friendly answers.
   - Built with FastAPI (Python) and a Spring Boot proxy.
4. **ETL Nodes (`ETL-node` / `python-etl-api`)**: 
   - Extracts ingredients from new recipes, uses a local AI model (`SentenceTransformer`) to convert them to vectors, and calculates nutritional data.
5. **API Gateway (`nginx`)**: 
   - A Layer 7 Load Balancer that routes external HTTP traffic evenly across the 3 Coordinator nodes.
6. **Frontend (`frontend`)**:
   - A React/Vite UI for interacting with the system.
7. **Vector Database (`qdrant`)**:
   - Stores recipe vectors and nutrition data for fast semantic search.

---

## ⚙️ Key Features

- **Semantic Vector Search**: Instead of simple text matching, the system converts ingredient names into vectors. For example, it knows that "1 crusty baguette" matches the "baguette" nutrition data.
- **Fault Tolerance**: If the Gemini API fails or times out due to high traffic, the system automatically retries the task without crashing.
- **Load Balancing**: Nginx distributes traffic across multiple Coordinator nodes, ensuring the system can handle many concurrent users.

---

## 🚀 How to Run (Manual Cluster)

This project provides an automated `.bat` script that opens all necessary terminals, starts the microservices, and automatically binds the cluster together.

1. **Clone the repository**.
2. **Create a `.env` file** in the directory /my-spring-project and add your API keys:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   QDRANT_API_KEY=your_qdrant_api_key_here
   ```
3. **Start the Cluster**:
   - run Docker
   - Navigate to the `.bat` directory.
   - Double click and run `start-system.bat`.
4. **Access the Application**:
   Open your browser and go to:
   ```text
   http://epicure.localhost
   ```
5. **For Admin mode (add Recipe)**
    Open your browser and go to:
   ```text
   http://epicure.localhost
   ```
   default password: admin123

---

### Node Ports Overview
- **COORDINATOR**: 8080, 8081, 8082
- **RECIPE-NODE**: 8100, 8101, 8102
- **LLM-NODE**: 8120, 8121
- **ETL-NODE**: 8140, 8141
