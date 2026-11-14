package com.example.recipenode.service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.example.recipenode.model.RecipeDocument;
import com.example.shared.model.Ingredient;
import com.example.shared.model.Nutrition;

@Component
public class RecipePayloadMapper {

    public RecipeDocument toDocument(Map<String, Object> payload) {
        List<Ingredient> ingredients = ingredients(payload);
        Integer explicitIngredientCount = getInteger(payload, "ingredient_count");
        Nutrition nutrition = extractNutrition(payload);

        return new RecipeDocument(
                getString(payload, "title"),
                getString(payload, "text"),
                getString(payload, "meal_type"),
                getString(payload, "cuisine"),
                getStringList(payload, "cooking_method"),
                getString(payload, "main_protein"),
                getStringList(payload, "diet_flags"),
                explicitIngredientCount != null ? explicitIngredientCount : (ingredients.isEmpty() ? null : ingredients.size()),
                getInteger(payload, "estimated_cook_time_min"),
                getBoolean(payload, "has_picture"),
                ingredients,
                nutrition,
                payload
        );
    }

    private Nutrition extractNutrition(Map<String, Object> payload) {
        // Look for flat keys first, or nested if applicable. The sample uses flat keys like "nutrition_total.calories"
        return new Nutrition(
                getDouble(payload, "nutrition_total.calories"),
                getDouble(payload, "nutrition_total.protein"),
                getDouble(payload, "nutrition_total.fat"),
                getDouble(payload, "nutrition_total.carbs"),
                getDouble(payload, "nutrition_total.fiber"),
                getDouble(payload, "nutrition_total.sugar"),
                getDouble(payload, "nutrition_total.sodium_mg")
        );
    }

    private Double getDouble(Map<String, Object> payload, String key) {
        if (payload == null) return null;
        if (payload.containsKey(key)) {
            return toDouble(payload.get(key));
        }
        if (key.contains(".")) {
            String[] parts = key.split("\\.");
            Map<String, Object> current = payload;
            for (int i = 0; i < parts.length - 1; i++) {
                Object val = current.get(parts[i]);
                if (val instanceof Map<?, ?> map) {
                    current = (Map<String, Object>) map;
                } else {
                    return null;
                }
            }
            return toDouble(current.get(parts[parts.length - 1]));
        }
        return null;
    }

    private String getString(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value != null ? String.valueOf(value) : null;
    }

    private Integer getInteger(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String text && !text.isBlank()) {
            try {
                return Double.valueOf(text).intValue();
            } catch (NumberFormatException ignored) {}
        }
        return null;
    }

    private Boolean getBoolean(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value instanceof Boolean bool) {
            return bool;
        }
        if (value instanceof String text && !text.isBlank()) {
            return Boolean.valueOf(text);
        }
        return null;
    }

    private List<String> getStringList(Map<String, Object> payload, String key) {
        List<String> result = new ArrayList<>();
        Object value = payload.get(key);
        if (value instanceof Collection<?> collection) {
            collection.stream()
                    .map(v -> v == null ? null : String.valueOf(v))
                    .forEach(result::add);
        } else if (value != null) {
            result.add(String.valueOf(value));
        }
        return result;
    }

    private List<Double> getDoubleList(Map<String, Object> payload, String key) {
        List<Double> result = new ArrayList<>();
        Object value = payload.get(key);
        if (value instanceof Collection<?> collection) {
            collection.stream()
                    .map(this::toDouble)
                    .forEach(result::add);
        } else if (value != null) {
            Double parsed = toDouble(value);
            result.add(parsed);
        }
        return result;
    }

    private List<Ingredient> ingredients(Map<String, Object> payload) {
        Object parsedObj = payload.get("parsed_ingredients");
        if (parsedObj instanceof Collection<?> collection) {
            List<Ingredient> ingredients = new ArrayList<>();
            for (Object item : collection) {
                if (item instanceof Map<?, ?> map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> ingMap = (Map<String, Object>) map;
                    String name = getString(ingMap, "name");
                    Double quantity = getDouble(ingMap, "quantity");
                    String unit = getString(ingMap, "unit");
                    ingredients.add(new Ingredient(name, quantity, unit));
                }
            }
            if (!ingredients.isEmpty()) {
                return ingredients;
            }
        }

        List<String> names = getStringList(payload, "ingredients_list");
        List<String> units = getStringList(payload, "units_list");
        List<Double> quantities = getDoubleList(payload, "quantities_list");

        List<Ingredient> ingredients = new ArrayList<>(names.size());
        for (int i = 0; i < names.size(); i++) {
            Double quantity = i < quantities.size() ? quantities.get(i) : null;
            String unit = i < units.size() ? units.get(i) : null;
            ingredients.add(new Ingredient(names.get(i), quantity, unit));
        }
        return ingredients;
    }

    private Double toDouble(Object value) {
        if (value instanceof Number number) return number.doubleValue();
        if (value instanceof String text && !text.isBlank()) {
            try { return Double.valueOf(text); } 
            catch (NumberFormatException ignored) {}
        }
        return null;
    }
}
