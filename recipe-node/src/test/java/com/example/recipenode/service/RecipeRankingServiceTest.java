package com.example.recipenode.service;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import org.junit.jupiter.api.Test;

import com.example.recipenode.model.RecipeCandidate;
import com.example.shared.model.RecipeFilters;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

class RecipeRankingServiceTest {
    private final RecipeRankingService rankingService = new RecipeRankingService(new RecipePayloadMapper());

    @Test
    void filtersAndRanksCandidatesWithApplicationScore() {
        RecipeQuery query = new RecipeQuery();
        query.setRecipeQuery("high protein low carb chicken dinner");

        RecipeFilters filters = new RecipeFilters();
        filters.setMealType("main_course");
        filters.setMainProtein("chicken");
        filters.setMaxCookTime(30);
        filters.setHasPicture(true);
        query.setFilters(filters);

        RecipeCandidate fastChicken = new RecipeCandidate("1", 0.82, Map.of(
                "title", "Fast Chicken Bowl",
                "meal_type", "main_course",
                "main_protein", "chicken",
                "estimated_cook_time_min", 25,
                "has_picture", true,
                "ingredients_list", List.of("chicken breast", "broccoli", "low carb sauce"),
                "units_list", List.of("g", "g", "tbsp"),
                "quantities_list", List.of(200.0, 120.0, 1.0)
        ));
        RecipeCandidate slowChicken = new RecipeCandidate("2", 0.95, Map.of(
                "title", "Slow Chicken Dinner",
                "meal_type", "main_course",
                "main_protein", "chicken",
                "estimated_cook_time_min", 55,
                "has_picture", true,
                "ingredients_list", List.of("chicken", "rice")
        ));
        RecipeCandidate fish = new RecipeCandidate("3", 0.99, Map.of(
                "title", "Fish Dinner",
                "meal_type", "main_course",
                "main_protein", "fish",
                "estimated_cook_time_min", 20,
                "has_picture", true
        ));

        List<RecipeQueryResult> results = rankingService.rank(query, List.of(slowChicken, fish, fastChicken), 10);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).getItemName()).isEqualTo("Fast Chicken Bowl");
        assertThat(results.get(0).getIngredients())
                .extracting("name")
                .containsExactly("chicken breast", "broccoli", "low carb sauce");
        assertThat(results.get(0).getIngredients())
                .extracting("unit")
                .containsExactly("g", "g", "tbsp");
        assertThat(results.get(0).getIngredients())
                .extracting("quantity")
                .containsExactly(200.0, 120.0, 1.0);
        assertThat(results.get(0).getMetadata())
                .containsEntry("qdrantScore", 0.82)
                .containsEntry("cookTime", 25)
                .containsEntry("mainProtein", "chicken")
                .containsEntry("ingredientCount", 3)
                .containsEntry("matchedFilters", 4);
    }

    @Test
    void filtersByNutritionHardLimits() {
        RecipeQuery query = new RecipeQuery();
        query.setRecipeQuery("healthy dinner");

        RecipeFilters filters = new RecipeFilters();
        filters.setMaxCalories(500.0);
        filters.setMinProtein(30.0);
        query.setFilters(filters);

        // Good recipe: 450 calories, 35 protein -> Should pass
        RecipeCandidate goodRecipe = new RecipeCandidate("1", 0.90, Map.of(
                "title", "Good Healthy Chicken",
                "nutrition_total.calories", 450.0,
                "nutrition_total.protein", 35.0
        ));

        // Bad calories recipe: 600 calories, 40 protein -> Should fail (max calories is 500)
        RecipeCandidate badCaloriesRecipe = new RecipeCandidate("2", 0.95, Map.of(
                "title", "High Calorie Chicken",
                "nutrition_total.calories", 600.0,
                "nutrition_total.protein", 40.0
        ));

        // Bad protein recipe: 400 calories, 20 protein -> Should fail (min protein is 30)
        RecipeCandidate badProteinRecipe = new RecipeCandidate("3", 0.99, Map.of(
                "title", "Low Protein Salad",
                "nutrition_total.calories", 400.0,
                "nutrition_total.protein", 20.0
        ));

        // Missing nutrition info -> Should fail because filters are strict
        RecipeCandidate noNutritionRecipe = new RecipeCandidate("4", 0.88, Map.of(
                "title", "Mystery Meal"
        ));

        List<RecipeQueryResult> results = rankingService.rank(query, List.of(goodRecipe, badCaloriesRecipe, badProteinRecipe, noNutritionRecipe), 10);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).getItemName()).isEqualTo("Good Healthy Chicken");
        assertThat(results.get(0).getNutrition().getCalories()).isEqualTo(450.0);
        assertThat(results.get(0).getNutrition().getProtein()).isEqualTo(35.0);
    }
}
