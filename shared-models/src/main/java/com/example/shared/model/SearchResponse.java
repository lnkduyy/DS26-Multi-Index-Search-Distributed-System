package com.example.shared.model;

import java.util.List;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class SearchResponse {
    private String answer;
    private List<RecipeQueryResult> recipes;
    private StatusState state;

    public SearchResponse() {}

    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }

    public List<RecipeQueryResult> getRecipes() { return recipes; }
    public void setRecipes(List<RecipeQueryResult> recipes) { this.recipes = recipes; }

    public StatusState getState() { return state; }
    public void setState(StatusState state) { this.state = state; }
}