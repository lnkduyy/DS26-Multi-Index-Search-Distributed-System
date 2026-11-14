# Coordinator Node

The `coordinator` is a Java/Spring Boot microservice that acts as the central orchestrator of the distributed system. It manages the state of long-running tasks and coordinates communication between the frontend and the AI nodes.

## 🌟 Key Features

1. **Raft-Like Leader Election**:
   - Because we run 3 instances of the coordinator (for high availability), they need to decide who is the "boss".
   - The nodes ping each other. If the leader goes offline, the remaining nodes hold an election to choose a new leader automatically.
2. **Task Queues & State Management**:
   - Some AI tasks (like processing a new recipe) take time. The coordinator puts these tasks into a background queue.
   - It assigns a UUID to each task so the frontend can poll for the `PENDING` or `SUCCESS` status asynchronously.
3. **Fault Tolerance & Retries**:
   - External AI APIs (like Gemini) can fail or time out during high traffic.
   - The coordinator wraps these API calls in a smart Retry mechanism. If a call fails, it will wait 5 seconds and try again, ensuring the system doesn't crash from temporary network issues.

## 🧩 How It Works

When a user searches for a recipe, the Coordinator:
1. Receives the HTTP request from Nginx.
2. Forwards the query to the `llm-node` to extract the search intent.
3. Forwards the extracted intent to the `recipe-node` to perform a semantic vector search in Qdrant.
4. Forwards the search results back to the `llm-node` to generate a natural, conversational answer for the user.
5. Returns the final JSON response to the frontend.

## 🚀 How to Run

This node is automatically managed by Docker Compose. You do not need to start it manually.

```bash
cd ..
docker-compose up -d --build coordinator-1 coordinator-2 coordinator-3
```

*(By default, the 3 nodes run internally on ports 8080, 8081, and 8082, but they are unified behind Nginx on port 80).*
