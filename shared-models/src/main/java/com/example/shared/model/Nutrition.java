package com.example.shared.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class Nutrition {
    private Double calories;
    private Double protein;
    private Double fat;
    private Double carbs;
    private Double fiber;
    private Double sugar;
    private Double sodiumMg;

    public Nutrition() {}

    public Nutrition(Double calories, Double protein, Double fat, Double carbs, Double fiber, Double sugar, Double sodiumMg) {
        this.calories = calories;
        this.protein = protein;
        this.fat = fat;
        this.carbs = carbs;
        this.fiber = fiber;
        this.sugar = sugar;
        this.sodiumMg = sodiumMg;
    }

    public Double getCalories() { return calories; }
    public void setCalories(Double calories) { this.calories = calories; }

    public Double getProtein() { return protein; }
    public void setProtein(Double protein) { this.protein = protein; }

    public Double getFat() { return fat; }
    public void setFat(Double fat) { this.fat = fat; }

    public Double getCarbs() { return carbs; }
    public void setCarbs(Double carbs) { this.carbs = carbs; }

    public Double getFiber() { return fiber; }
    public void setFiber(Double fiber) { this.fiber = fiber; }

    public Double getSugar() { return sugar; }
    public void setSugar(Double sugar) { this.sugar = sugar; }

    public Double getSodiumMg() { return sodiumMg; }
    public void setSodiumMg(Double sodiumMg) { this.sodiumMg = sodiumMg; }
}
