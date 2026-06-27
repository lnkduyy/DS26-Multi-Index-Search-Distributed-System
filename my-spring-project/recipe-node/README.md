# Recipe Node

`recipe-node` is a Spring Boot microservice that acts as the "search engine" within the distributed system. It receives semantic search queries, searches the **Qdrant** vector database, and applies a multi-factor ranking algorithm to return the best matching recipes.

## 🧩 Data Flow Architecture

1. Receives a search request containing a structured `RecipeQuery` from the Coordinator.
2. Calls the `QdrantRecipeRepository` to perform a semantic vector search via gRPC to Qdrant.
3. Passes the results to the `RecipeRankingService` to recalculate and rescore the matches.
4. Returns the Top-K best recipes along with their nutritional information.

---

## 🌟 Key Features

### Multi-Factor Ranking Algorithm
To ensure the best recipes are returned to the user, the node doesn't just rely on the AI's semantic score. It recalculates the final score based on 5 weighted factors:
- **40%**: Semantic Vector Score (from Qdrant)
- **20%**: Title match relevance
- **20%**: Ingredient overlap (how many requested ingredients are actually in the recipe)
- **10%**: Cook time penalty (penalizes recipes that take longer than requested)
- **10%**: Main protein relevance

---

## 🚀 How to Run

This node is automatically managed by Docker Compose. You do not need to start it manually.

```bash
cd ..
docker-compose up -d --build recipe-node-1 recipe-node-2
```

*(By default, the 2 nodes run internally on ports 8081/8082, but they receive their traffic via the Coordinator).*
