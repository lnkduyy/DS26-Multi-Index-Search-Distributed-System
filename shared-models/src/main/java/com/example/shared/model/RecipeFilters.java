package com.example.shared.model;

import java.util.ArrayList;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class RecipeFilters {
    private String mealType;
    private String cuisine;
    private List<String> cookingMethod;
    private String mainProtein;
    private List<String> dietFlags;
    private Integer maxIngredients;
    private Integer maxCookTime;
    private Boolean hasPicture;

    // Nutrition Filters
    private Double maxCalories;          
    private Double minProtein;          
    private Double maxFat;     
    private Double maxCarbs;           
    private Double minFiber;          
    private Double maxSugar;        
    private Double maxSodium;          
    private Boolean isHighProtein;     
    private Boolean isLowCarb;      
    private Boolean isLowCalorie;

    // Parallel arrays from LLM response
    private List<String> ingredientsList;
    private List<String> ingredientUnits;
    private List<Double> ingredientQuantities;

    public RecipeFilters() {}

    @JsonIgnore
    public List<Ingredient> getIngredients() {
        if (ingredientsList == null) {
            return List.of();
        }
        List<Ingredient> list = new ArrayList<>(ingredientsList.size());
        for (int i = 0; i < ingredientsList.size(); i++) {
            String name = ingredientsList.get(i);
            String unit = (ingredientUnits != null && i < ingredientUnits.size()) ? ingredientUnits.get(i) : null;
            Double qty = (ingredientQuantities != null && i < ingredientQuantities.size()) ? ingredientQuantities.get(i) : null;
            list.add(new Ingredient(name, qty, unit));
        }
        return list;
    }

    public String getMealType() { return mealType; }
    public void setMealType(String mealType) { this.mealType = mealType; }

    public String getCuisine() { return cuisine; }
    public void setCuisine(String cuisine) { this.cuisine = cuisine; }

    public List<String> getCookingMethod() { return cookingMethod; }
    public void setCookingMethod(List<String> cookingMethod) { this.cookingMethod = cookingMethod; }

    public String getMainProtein() { return mainProtein; }
    public void setMainProtein(String mainProtein) { this.mainProtein = mainProtein; }

    public List<String> getDietFlags() { return dietFlags; }
    public void setDietFlags(List<String> dietFlags) { this.dietFlags = dietFlags; }

    public Integer getMaxIngredients() { return maxIngredients; }
    public void setMaxIngredients(Integer maxIngredients) { this.maxIngredients = maxIngredients; }

    public Integer getMaxCookTime() { return maxCookTime; }
    public void setMaxCookTime(Integer maxCookTime) { this.maxCookTime = maxCookTime; }

    public Boolean getHasPicture() { return hasPicture; }
    public void setHasPicture(Boolean hasPicture) { this.hasPicture = hasPicture; }

    public Double getMaxCalories() { return maxCalories; }
    public void setMaxCalories(Double maxCalories) { this.maxCalories = maxCalories; }

    public Double getMinProtein() { return minProtein; }
    public void setMinProtein(Double minProtein) { this.minProtein = minProtein; }

    public Double getMaxFat() { return maxFat; }
    public void setMaxFat(Double maxFat) { this.maxFat = maxFat; }

    public Double getMaxCarbs() { return maxCarbs; }
    public void setMaxCarbs(Double maxCarbs) { this.maxCarbs = maxCarbs; }

    public Double getMinFiber() { return minFiber; }
    public void setMinFiber(Double minFiber) { this.minFiber = minFiber; }

    public Double getMaxSugar() { return maxSugar; }
    public void setMaxSugar(Double maxSugar) { this.maxSugar = maxSugar; }

    public Double getMaxSodium() { return maxSodium; }
    public void setMaxSodium(Double maxSodium) { this.maxSodium = maxSodium; }

    public Boolean getIsHighProtein() { return isHighProtein; }
    public void setIsHighProtein(Boolean isHighProtein) { this.isHighProtein = isHighProtein; }

    public Boolean getIsLowCarb() { return isLowCarb; }
    public void setIsLowCarb(Boolean isLowCarb) { this.isLowCarb = isLowCarb; }

    public Boolean getIsLowCalorie() { return isLowCalorie; }
    public void setIsLowCalorie(Boolean isLowCalorie) { this.isLowCalorie = isLowCalorie; }

    public List<String> getIngredientsList() { return ingredientsList; }
    public void setIngredientsList(List<String> ingredientsList) { this.ingredientsList = ingredientsList; }

    public List<String> getIngredientUnits() { return ingredientUnits; }
    public void setIngredientUnits(List<String> ingredientUnits) { this.ingredientUnits = ingredientUnits; }

    public List<Double> getIngredientQuantities() { return ingredientQuantities; }
    public void setIngredientQuantities(List<Double> ingredientQuantities) { this.ingredientQuantities = ingredientQuantities; }
}
