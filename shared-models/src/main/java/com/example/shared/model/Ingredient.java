package com.example.shared.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class Ingredient {
    private String name;
    private Double quantity;
    private String unit;

    public Ingredient() {}

    public Ingredient(String name, Double quantity, String unit) {
        this.name = name;
        this.quantity = quantity;
        this.unit = unit;
    }

    public String getName() { return name;}
    public void setName(String name) { this.name = name;}

    public Double getQuantity() { return quantity;}
    public void setQuantity(Double quantity) { this.quantity = quantity;}

    public String getUnit() { return unit;}
    public void setUnit(String unit) { this.unit = unit;}
}
