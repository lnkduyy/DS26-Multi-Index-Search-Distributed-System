package com.example.recipenode.model;

import java.util.Map;

public record RecipeCandidate(String id, double qdrantScore, Map<String, Object> payload) {}
