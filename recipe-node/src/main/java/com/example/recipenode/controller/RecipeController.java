package com.example.recipenode.controller;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.recipenode.service.RecipeService;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/recipes")
public class RecipeController {
    private final RecipeService RecipeService;

    public RecipeController(RecipeService RecipeService) {
        this.RecipeService = RecipeService;
    }

    @PostMapping("/search")
    ResponseEntity<List<RecipeQueryResult>> search(@Valid @RequestBody RecipeQuery query) {
        return ResponseEntity.ok(RecipeService.search(query));
    }

    // ---- add ETL-node ---
    @PostMapping("/ingest")
    public ResponseEntity<String> ingest(@RequestBody com.example.shared.model.ETLQueryResult result) {
        RecipeService.ingest(result.getChunks());
        return ResponseEntity.ok("Ingested successfully");
    }
    // --- add ETL-node ----
}
