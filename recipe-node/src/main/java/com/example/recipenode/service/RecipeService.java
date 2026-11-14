package com.example.recipenode.service;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.example.recipenode.config.RecipeNodeProperties;
import com.example.recipenode.model.RecipeCandidate;
import com.example.recipenode.repository.QdrantRecipeRepository;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

@Service
public class RecipeService {
    private static final Logger log = LoggerFactory.getLogger(RecipeService.class);
    private final QdrantRecipeRepository recipeRepository;
    private final RecipeRankingService rankingService;
    private final RecipeNodeProperties properties;

    public RecipeService(
            QdrantRecipeRepository recipeRepository,
            RecipeRankingService rankingService,
            RecipeNodeProperties properties
    ) {
        this.recipeRepository = recipeRepository;
        this.rankingService = rankingService;
        this.properties = properties;
    }

    public List<RecipeQueryResult> search(RecipeQuery query) {
        if (query == null || query.getRecipeQuery() == null || query.getRecipeQuery().isBlank()) {
            log.warn("Search called with null or blank query");
            throw new IllegalArgumentException("Blank query");
        }

        long startTime = System.currentTimeMillis();
        List<RecipeCandidate> candidates = recipeRepository.findCandidates(query.getRecipeQuery());
        List<RecipeQueryResult> results = rankingService.rank(query, candidates, properties.topK());
        log.info("Search completed in {}ms — query='{}', candidates={}, results={}",
                System.currentTimeMillis() - startTime, query.getRecipeQuery(), candidates.size(), results.size());
        return results;
    }

    // ---- add ETL-node ---
    public void ingest(List<java.util.Map<String, Object>> chunks) {
        if (chunks == null || chunks.isEmpty()) return;
        recipeRepository.upsertChunks(chunks);
    }
    // --- add ETL-node ----
}
