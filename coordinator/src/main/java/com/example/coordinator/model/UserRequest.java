package com.example.coordinator.model;

import java.time.LocalDateTime;
import java.util.List;

import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

public class UserRequest {
    private String id;
    private String state;
    private LocalDateTime ttl;
    private String userQuery;
    private RecipeQuery recipeQuery;
    private List<RecipeQueryResult> recipeQueryResults;
    private String result;
    // ---- add ETL-node ---
    private String type;
    private com.example.shared.model.ETLQuery.Dish ingestDish;
    // --- add ETL-node ----

    public UserRequest() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getState() { return state; }
    public void setState(String state) { this.state = state; }

    public LocalDateTime getTtl() { return ttl; }
    public void setTtl(LocalDateTime ttl) { this.ttl = ttl; }

    public String getUserQuery() { return userQuery; }
    public void setUserQuery(String userQuery) { this.userQuery = userQuery; }

    public RecipeQuery getRecipeQuery() { return recipeQuery; }
    public void setRecipeQuery(RecipeQuery recipeQuery) { this.recipeQuery = recipeQuery; }

    public List<RecipeQueryResult> getRecipeQueryResults() { return recipeQueryResults; }
    public void setRecipeQueryResults(List<RecipeQueryResult> recipeQueryResults) { this.recipeQueryResults = recipeQueryResults; }

    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }

    // ---- add ETL-node ---
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public com.example.shared.model.ETLQuery.Dish getIngestDish() { return ingestDish; }
    public void setIngestDish(com.example.shared.model.ETLQuery.Dish ingestDish) { this.ingestDish = ingestDish; }
    // --- add ETL-node ----
}