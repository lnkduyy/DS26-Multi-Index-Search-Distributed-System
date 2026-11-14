# ETL Pipeline Node

This folder contains the ETL (Extract, Transform, Load) components of the Distributed System. It is responsible for intercepting new recipes, parsing their ingredients, and connecting to Qdrant to calculate enriched nutritional metadata before the data is ingested into the database.

The ETL pipeline consists of two tightly coupled services:
1. **Python API (`etl-api`)**: Performs the heavy lifting (parsing logic, AI vector generation, math).
2. **Java Spring Boot Node (Root)**: Exposes the ETL service to the rest of the Java-based distributed system and orchestrates the calls.

---

## 🌟 Key Features

### Semantic Vector Search for Nutrition
Instead of relying on strict text matching (where "1 crusty baguette" would fail to match "baguette"), this node uses a **Semantic Vector Search**.
- It uses a local AI model (`SentenceTransformer/all-MiniLM-L6-v2`) to convert messy ingredient strings into mathematical vectors.
- It queries the Qdrant database to find the closest semantic match in the nutrition collection, ensuring highly accurate calorie and macro calculations.

### Asynchronous Ingestion
Because AI processing and vector searches are slow, the ETL node is designed to process data asynchronously. The Coordinator hands the job to the ETL Node, which processes it in the background and reports back when finished.

---

## 🚀 How to Run

This node is automatically managed by Docker Compose. You do not need to start it manually.

```bash
cd ..
docker-compose up -d --build etl-node-1 etl-node-2 python-etl-api
```

*(By default, the Java nodes run internally on ports 8140/8141, and the Python API runs on port 6000).*
