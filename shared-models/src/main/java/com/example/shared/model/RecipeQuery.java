package com.example.shared.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class RecipeQuery {
    private String recipeQuery;
    private RecipeFilters filters;
    private StatusState state;

    public RecipeQuery() {}

    public String getRecipeQuery() { return recipeQuery; }
    public void setRecipeQuery(String recipeQuery) { this.recipeQuery = recipeQuery; }

    public RecipeFilters getFilters() { return filters; }
    public void setFilters(RecipeFilters filters) { this.filters = filters; }

    public StatusState getState() { return state; }
    public void setState(StatusState state) { this.state = state; }
}