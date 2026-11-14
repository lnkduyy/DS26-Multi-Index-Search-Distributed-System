package com.example.recipenode.model;

import java.util.List;
import java.util.Map;

import com.example.shared.model.Ingredient;
import com.example.shared.model.Nutrition;

public record RecipeDocument(
        String itemName,
        String payloadText,
        String mealType,
        String cuisine,
        List<String> cookingMethods,
        String mainProtein,
        List<String> dietFlags,
        Integer ingredientCount,
        Integer cookTime,
        Boolean hasPicture,
        List<Ingredient> ingredients,
        Nutrition nutrition,
        Map<String, Object> rawPayload
) {
}
