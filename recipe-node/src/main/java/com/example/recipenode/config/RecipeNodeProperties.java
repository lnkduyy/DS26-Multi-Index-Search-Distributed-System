package com.example.recipenode.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

@Validated
@ConfigurationProperties(prefix = "recipe-search")
public record RecipeNodeProperties(
        Qdrant qdrant,
        @Min(1) @Max(1000) int candidateLimit,
        @Min(1) @Max(100) int topK,
        @Min(1) @Max(300) int queryTimeoutSeconds
) {
    public RecipeNodeProperties {
        if (qdrant == null) {
            throw new IllegalArgumentException("Qdrant configuration (recipe-search.qdrant) is missing in application.yml");
        }
    }

    public record Qdrant(
            @NotBlank String host,
            @Min(1) @Max(65535) int port,
            boolean tls,
            String apiKey,
            @NotBlank String collection,
            String vectorName,
            @NotBlank String inferenceModel
    ) {
    }
}
