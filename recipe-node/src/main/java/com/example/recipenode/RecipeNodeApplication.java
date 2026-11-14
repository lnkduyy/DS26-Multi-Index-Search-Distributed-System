package com.example.recipenode;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication(scanBasePackages = {"com.example.recipenode", "com.example.shared"})
@ConfigurationPropertiesScan
public class RecipeNodeApplication {
    public static void main(String[] args) {
        SpringApplication.run(RecipeNodeApplication.class, args);
    }
}
