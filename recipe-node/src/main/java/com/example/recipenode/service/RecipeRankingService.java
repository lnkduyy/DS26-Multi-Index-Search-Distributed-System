package com.example.recipenode.service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.example.recipenode.model.RecipeCandidate;
import com.example.recipenode.model.RecipeDocument;
import com.example.shared.model.Ingredient;
import com.example.shared.model.RecipeFilters;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

@Service
public class RecipeRankingService {
    private static final Logger log = LoggerFactory.getLogger(RecipeRankingService.class);
    private static final Pattern TOKEN_SPLIT = Pattern.compile("[^a-z0-9]+");
    private static final double WEIGHT_QDRANT_SCORE = 0.35;
    private static final double WEIGHT_TITLE_RELEVANCE = 0.15;
    private static final double WEIGHT_INGREDIENT_OVERLAP = 0.15;
    private static final double WEIGHT_INVENTORY_MATCH = 0.20;
    private static final double WEIGHT_COOK_TIME = 0.10;
    private static final double WEIGHT_PROTEIN_RELEVANCE = 0.05;
    private static final double COOK_TIME_CEILING = 1.2;
    private static final double PARTIAL_PROTEIN_SCORE = 0.75;
    private static final double PARTIAL_TITLE_SCORE = 0.8;
    private static final int MIN_TOKEN_LENGTH = 2;
    private static final double HIGH_PROTEIN_THRESHOLD = 20.0;
    private static final double LOW_CARB_THRESHOLD = 20.0;
    private static final double LOW_CALORIE_THRESHOLD = 400.0;

    private final RecipePayloadMapper payloadMapper;

    public RecipeRankingService(RecipePayloadMapper payloadMapper) {
        this.payloadMapper = payloadMapper;
    }

    public List<RecipeQueryResult> rank(RecipeQuery query, List<RecipeCandidate> candidates, int topK) {
        RecipeFilters filters = query.getFilters();
        String rawQuery = query.getRecipeQuery() != null ? query.getRecipeQuery() : "";
        Set<String> queryTerms = tokenize(rawQuery);

        // ---- duplicate remove ---
        Set<String> seenNames = new java.util.HashSet<>();
        // --- duplicate remove ----

        List<RecipeQueryResult> results = candidates.stream()
                .map(candidate -> new RankedCandidate(candidate, payloadMapper.toDocument(candidate.payload())))
                .filter(candidate -> matchesFilters(candidate.document(), filters))
                .map(candidate -> toRankedResult(candidate, filters, queryTerms, rawQuery))
                .sorted(Comparator.comparing(RecipeQueryResult::getScore, Comparator.nullsLast(Double::compareTo)).reversed())
                // ---- duplicate remove ---
                .filter(result -> {
                    String name = result.getItemName() != null ? result.getItemName().toLowerCase(Locale.ROOT).trim() : "";
                    return seenNames.add(name);
                })
                // --- duplicate remove ----
                .limit(topK)
                .toList();

        log.info("Ranked {} candidates → {} results (topK={}, query='{}')",
                candidates.size(), results.size(), topK, rawQuery);
        return results;
    }

    private RecipeQueryResult toRankedResult(
            RankedCandidate rankedCandidate,
            RecipeFilters filters,
            Set<String> queryTerms,
            String rawQuery
    ) {
        RecipeCandidate candidate = rankedCandidate.candidate();
        RecipeDocument document = rankedCandidate.document();
        
        List<Ingredient> missingIngredients = calculateMissingIngredients(document.ingredients(), filters);
        
        double qdrantScore = normalize(candidate.qdrantScore());
        double titleRelevance = titleRelevance(rawQuery, queryTerms, document);
        double ingredientOverlap = ingredientOverlap(queryTerms, document);
        double cookTimePreference = cookTimePreference(filters, document);
        double proteinRelevance = proteinRelevance(filters, document, queryTerms);
        double inventoryMatch = calculateInventoryMatch(document.ingredients(), missingIngredients, filters);

        // Adjust weights to include titleRelevance and inventoryMatch
        double finalScore =
                (qdrantScore * WEIGHT_QDRANT_SCORE)
                        + (titleRelevance * WEIGHT_TITLE_RELEVANCE)
                        + (ingredientOverlap * WEIGHT_INGREDIENT_OVERLAP)
                        + (inventoryMatch * WEIGHT_INVENTORY_MATCH)
                        + (cookTimePreference * WEIGHT_COOK_TIME)
                        + (proteinRelevance * WEIGHT_PROTEIN_RELEVANCE);

        RecipeQueryResult result = new RecipeQueryResult();
        result.setItemName(document.itemName());
        result.setPayload(document.payloadText());
        result.setScore(round(finalScore));
        result.setIngredients(document.ingredients());
        result.setMissingIngredients(missingIngredients);
        result.setNutrition(document.nutrition());
        result.setMetadata(metadata(candidate, document, countMatchedFilters(document, filters), titleRelevance));
        return result;
    }

    private double calculateInventoryMatch(List<Ingredient> recipeIngredients, List<Ingredient> missingIngredients, RecipeFilters filters) {
        if (filters == null || filters.getIngredients() == null || filters.getIngredients().isEmpty()) {
            return 1.0; // If user didn't specify what they have, we don't penalize.
        }
        if (recipeIngredients == null || recipeIngredients.isEmpty()) {
            return 0.5;
        }
        return Math.max(0.0, 1.0 - ((double) missingIngredients.size() / recipeIngredients.size()));
    }

    private List<Ingredient> calculateMissingIngredients(List<Ingredient> recipeIngredients, RecipeFilters filters) {
        if (recipeIngredients == null || recipeIngredients.isEmpty()) return List.of();
        if (filters == null || filters.getIngredients() == null || filters.getIngredients().isEmpty()) return recipeIngredients;

        List<Ingredient> userIngredients = filters.getIngredients();
        record UserIngredientEntry(Double quantity, String unit) {}
        Map<String, UserIngredientEntry> userInventory = new LinkedHashMap<>();
        
        for (Ingredient ui : userIngredients) {
            if (ui.getName() == null) continue;
            String normName = normalizeText(ui.getName());
            userInventory.put(normName, new UserIngredientEntry(ui.getQuantity(), ui.getUnit()));
        }

        List<Ingredient> missing = new ArrayList<>();
        for (Ingredient ri : recipeIngredients) {
            if (ri.getName() == null) continue;
            String normRecipeName = normalizeText(ri.getName());
            
            boolean found = false;
            // Fuzzy match: check if recipe ingredient name is contained in user ingredient name or vice versa
            for (Map.Entry<String, UserIngredientEntry> entry : userInventory.entrySet()) {
                if (normRecipeName.contains(entry.getKey()) || entry.getKey().contains(normRecipeName)) {
                    found = true;
                    UserIngredientEntry userEntry = entry.getValue();
                    if (ri.getQuantity() != null && userEntry.quantity() != null) {
                        // Only compare quantities when units match or are both absent
                        String riUnit = normalizeText(ri.getUnit());
                        String userUnit = normalizeText(userEntry.unit());
                        if (riUnit.equals(userUnit) || riUnit.isEmpty() || userUnit.isEmpty()) {
                            double missingQty = ri.getQuantity() - userEntry.quantity();
                            if (missingQty > 0) {
                                missing.add(new Ingredient(ri.getName(), missingQty, ri.getUnit()));
                            }
                        }
                    }
                    break;
                }
            }
            if (!found) {
                missing.add(ri);
            }
        }
        return missing;
    }

    private boolean matchesFilters(RecipeDocument document, RecipeFilters filters) {
        if (filters == null) {
            return true;
        }
        boolean basicMatch = equalsIfPresent(filters.getMealType(), document.mealType())
                && equalsIfPresent(filters.getCuisine(), document.cuisine())
                && anyIfPresent(filters.getCookingMethod(), document.cookingMethods())
                && equalsIfPresent(filters.getMainProtein(), document.mainProtein())
                && allIfPresent(filters.getDietFlags(), document.dietFlags())
                && lessOrEqualIfPresent(document.ingredientCount(), filters.getMaxIngredients())
                && lessOrEqualIfPresent(document.cookTime(), filters.getMaxCookTime())
                && equalsIfPresent(filters.getHasPicture(), document.hasPicture());

        if (!basicMatch) {
            return false;
        }

        if (document.nutrition() == null) {
            return !hasNutritionFilters(filters);
        }

        boolean nutritionMatch = lessOrEqualIfPresent(document.nutrition().getCalories(), filters.getMaxCalories())
                && greaterOrEqualIfPresent(document.nutrition().getProtein(), filters.getMinProtein())
                && lessOrEqualIfPresent(document.nutrition().getFat(), filters.getMaxFat())
                && lessOrEqualIfPresent(document.nutrition().getCarbs(), filters.getMaxCarbs())
                && greaterOrEqualIfPresent(document.nutrition().getFiber(), filters.getMinFiber())
                && lessOrEqualIfPresent(document.nutrition().getSugar(), filters.getMaxSugar())
                && lessOrEqualIfPresent(document.nutrition().getSodiumMg(), filters.getMaxSodium());

        if (!nutritionMatch) return false;

        // Boolean diet-type filters
        if (Boolean.TRUE.equals(filters.getIsHighProtein())
                && (document.nutrition().getProtein() == null || document.nutrition().getProtein() < HIGH_PROTEIN_THRESHOLD)) {
            return false;
        }
        if (Boolean.TRUE.equals(filters.getIsLowCarb())
                && (document.nutrition().getCarbs() == null || document.nutrition().getCarbs() > LOW_CARB_THRESHOLD)) {
            return false;
        }
        if (Boolean.TRUE.equals(filters.getIsLowCalorie())
                && (document.nutrition().getCalories() == null || document.nutrition().getCalories() > LOW_CALORIE_THRESHOLD)) {
            return false;
        }

        return true;
    }

    private boolean hasNutritionFilters(RecipeFilters filters) {
        return filters.getMaxCalories() != null || filters.getMinProtein() != null 
            || filters.getMaxFat() != null || filters.getMaxCarbs() != null 
            || filters.getMinFiber() != null || filters.getMaxSugar() != null 
            || filters.getMaxSodium() != null
            || Boolean.TRUE.equals(filters.getIsHighProtein())
            || Boolean.TRUE.equals(filters.getIsLowCarb())
            || Boolean.TRUE.equals(filters.getIsLowCalorie());
    }

    private Map<String, Object> metadata(RecipeCandidate candidate, RecipeDocument document, int matchedFilters, double titleRelevance) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("qdrantScore", round(candidate.qdrantScore()));
        metadata.put("titleRelevance", round(titleRelevance));
        metadata.put("cookTime", document.cookTime());
        metadata.put("mainProtein", document.mainProtein());
        metadata.put("ingredientCount", document.ingredientCount());
        metadata.put("matchedFilters", matchedFilters);
        metadata.put("qdrantPointId", candidate.id());
        return metadata;
    }

    private int countMatchedFilters(RecipeDocument document, RecipeFilters filters) {
        if (filters == null) {
            return 0;
        }
        int matched = 0;
        if (filters.getMealType() != null && equalsIfPresent(filters.getMealType(), document.mealType())) matched++;
        if (filters.getCuisine() != null && equalsIfPresent(filters.getCuisine(), document.cuisine())) matched++;
        if (filters.getCookingMethod() != null && anyIfPresent(filters.getCookingMethod(), document.cookingMethods())) matched++;
        if (filters.getMainProtein() != null && equalsIfPresent(filters.getMainProtein(), document.mainProtein())) matched++;
        if (filters.getDietFlags() != null && allIfPresent(filters.getDietFlags(), document.dietFlags())) matched++;
        if (filters.getMaxIngredients() != null && lessOrEqualIfPresent(document.ingredientCount(), filters.getMaxIngredients())) matched++;
        if (filters.getMaxCookTime() != null && lessOrEqualIfPresent(document.cookTime(), filters.getMaxCookTime())) matched++;
        if (filters.getHasPicture() != null && equalsIfPresent(filters.getHasPicture(), document.hasPicture())) matched++;
        return matched;
    }

    private double ingredientOverlap(Set<String> queryTerms, RecipeDocument document) {
        Set<String> ingredientTerms = tokenize(ingredientNames(document.ingredients()));
        if (queryTerms.isEmpty() || ingredientTerms.isEmpty()) {
            return 0.0;
        }
        long hits = ingredientTerms.stream().filter(queryTerms::contains).count();
        return Math.min(1.0, hits / (double) Math.min(queryTerms.size(), ingredientTerms.size()));
    }

    private double titleRelevance(String rawQuery, Set<String> queryTerms, RecipeDocument document) {
        String title = document.itemName();
        if (title == null || title.isBlank()) {
            return 0.0;
        }

        String normalizedTitle = normalizeText(title);
        String normalizedQuery = normalizeText(rawQuery);

        if (normalizedTitle.equals(normalizedQuery)) return 1.0;
        if (normalizedTitle.contains(normalizedQuery) || normalizedQuery.contains(normalizedTitle)) return PARTIAL_TITLE_SCORE;

        Set<String> titleTerms = tokenize(title);
        if (titleTerms.isEmpty() || queryTerms.isEmpty()) return 0.0;

        long hits = titleTerms.stream().filter(queryTerms::contains).count();
        return Math.min(1.0, hits / (double) Math.min(queryTerms.size(), titleTerms.size()));
    }

    private List<String> ingredientNames(List<Ingredient> ingredients) {
        return ingredients.stream()
                .map(Ingredient::getName)
                .filter(Objects::nonNull)
                .toList();
    }

    private double cookTimePreference(RecipeFilters filters, RecipeDocument document) {
        Integer cookTime = document.cookTime();
        if (cookTime == null) {
            return 0.5;
        }
        if (filters == null || filters.getMaxCookTime() == null || filters.getMaxCookTime() <= 0) {
            return 1.0;
        }
        double ratio = cookTime.doubleValue() / filters.getMaxCookTime();
        return Math.max(0.0, Math.min(1.0, COOK_TIME_CEILING - ratio));
    }

    private double proteinRelevance(RecipeFilters filters, RecipeDocument document, Set<String> queryTerms) {
        String protein = document.mainProtein();
        if (protein == null || protein.isBlank()) {
            return 0.0;
        }
        String normalizedProtein = normalizeText(protein);
        if (filters != null && filters.getMainProtein() != null
                && normalizeText(filters.getMainProtein()).equals(normalizedProtein)) {
            return 1.0;
        }
        return queryTerms.contains(normalizedProtein) ? PARTIAL_PROTEIN_SCORE : 0.0;
    }

    private boolean equalsIfPresent(String expected, String actual) {
        if (expected == null) return true;
        if (actual == null) return false;
        String normExpected = normalizeText(expected);
        String normActual = normalizeText(actual);
        return normExpected.equals(normActual) || normActual.contains(normExpected) || normExpected.contains(normActual);
    }

    private boolean equalsIfPresent(Boolean expected, Boolean actual) {
        return expected == null || Objects.equals(expected, actual);
    }

    private boolean lessOrEqualIfPresent(Number actual, Integer max) {
        return max == null || (actual != null && actual.doubleValue() <= max);
    }

    private boolean lessOrEqualIfPresent(Number actual, Double max) {
        return max == null || (actual != null && actual.doubleValue() <= max);
    }

    private boolean greaterOrEqualIfPresent(Number actual, Double min) {
        return min == null || (actual != null && actual.doubleValue() >= min);
    }

    private boolean anyIfPresent(Collection<String> expected, Collection<String> actual) {
        if (expected == null || expected.isEmpty()) {
            return true;
        }
        if (actual == null || actual.isEmpty()) return false;
        Set<String> normalizedActual = normalizeAll(actual);
        for (String exp : expected) {
            String normExp = normalizeText(exp);
            for (String act : normalizedActual) {
                if (act.equals(normExp) || act.contains(normExp) || normExp.contains(act)) {
                    return true;
                }
            }
        }
        return false;
    }

    private boolean allIfPresent(Collection<String> expected, Collection<String> actual) {
        if (expected == null || expected.isEmpty()) {
            return true;
        }
        if (actual == null || actual.isEmpty()) return false;
        Set<String> normalizedActual = normalizeAll(actual);
        for (String exp : expected) {
            String normExp = normalizeText(exp);
            boolean matchedExp = false;
            for (String act : normalizedActual) {
                if (act.equals(normExp) || act.contains(normExp) || normExp.contains(act)) {
                    matchedExp = true;
                    break;
                }
            }
            if (!matchedExp) return false;
        }
        return true;
    }

    private Set<String> normalizeAll(Collection<String> values) {
        if (values == null) return Set.of();
        Set<String> normalized = new LinkedHashSet<>();
        for (String value : values) {
            normalized.add(normalizeText(value));
        }
        return normalized;
    }

    private Set<String> tokenize(String text) {
        if (text == null || text.isBlank()) {
            return Set.of();
        }
        return tokenize(List.of(text));
    }

    private Set<String> tokenize(Collection<String> texts) {
        Set<String> terms = new LinkedHashSet<>();
        for (String text : texts) {
            if (text == null) {
                continue;
            }
            for (String token : TOKEN_SPLIT.split(text.toLowerCase(Locale.ROOT))) {
                if (token.length() >= MIN_TOKEN_LENGTH) {
                    terms.add(token);
                }
            }
        }
        return terms;
    }

    private String normalizeText(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT).replace('_', ' ');
    }

    private double normalize(double score) {
        if (score >= 0.0 && score <= 1.0) {
            return score;
        }
        return 1.0 / (1.0 + Math.exp(-score));
    }

    private double round(double value) {
        return Math.round(value * 10_000.0) / 10_000.0;
    }

    private record RankedCandidate(RecipeCandidate candidate, RecipeDocument document) {
    }
}
