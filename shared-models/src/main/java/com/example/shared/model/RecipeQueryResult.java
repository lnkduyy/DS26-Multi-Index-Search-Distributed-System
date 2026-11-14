package com.example.shared.model;

import java.util.List;
import java.util.Map;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class RecipeQueryResult {
    private String itemName;
    private String payload;
    private Double score;
    private List<Ingredient> ingredients;
    private List<Ingredient> missingIngredients;
    private Nutrition nutrition;
    private Map<String, Object> metadata;
    private StatusState state;

    public RecipeQueryResult() {}

    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }

    public String getPayload() { return payload; }
    public void setPayload(String payload) { this.payload = payload; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }

    public List<Ingredient> getIngredients() { return ingredients; }
    public void setIngredients(List<Ingredient> ingredients) { this.ingredients = ingredients; }

    public List<Ingredient> getMissingIngredients() { return missingIngredients; }
    public void setMissingIngredients(List<Ingredient> missingIngredients) { this.missingIngredients = missingIngredients; }

    public Nutrition getNutrition() { return nutrition; }
    public void setNutrition(Nutrition nutrition) { this.nutrition = nutrition; }

    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }

    public StatusState getState() { return state; }
    public void setState(StatusState state) { this.state = state; }
}
