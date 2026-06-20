package com.example.coordinator.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.client.RestTemplate;
import org.springframework.beans.factory.annotation.Value;

// ---- add ETL-node ---
import com.example.coordinator.model.UserRequest;
import com.example.coordinator.service.RequestStorage;
import java.time.LocalDateTime;
// --- add ETL-node ----

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/dishes")
public class DishController {
    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;
    // ---- add ETL-node ---
    private final com.example.coordinator.service.ProcessingService processingService;
    private final RequestStorage storage;
    private final com.example.coordinator.service.ConsensusService consensusService;
    // --- add ETL-node ----
    private final Path dishesFile = Path.of("data", "dishes.json");
    private final Object lock = new Object();

    @Value("${admin.token}")
    private String adminToken;

    public DishController(ObjectMapper objectMapper, RestTemplate restTemplate, com.example.coordinator.service.ProcessingService processingService, RequestStorage storage, com.example.coordinator.service.ConsensusService consensusService) {
        this.objectMapper = objectMapper.copy().enable(SerializationFeature.INDENT_OUTPUT);
        this.restTemplate = restTemplate;
        // ---- add ETL-node ---
        this.processingService = processingService;
        this.storage = storage;
        this.consensusService = consensusService;
        // --- add ETL-node ----
        ensureDishesFile();
    }

    @GetMapping
    public List<Dish> dishes() {
        java.util.Map<String, RecipeRecord> map = readDishes();
        List<Dish> list = new ArrayList<>();
        for (java.util.Map.Entry<String, RecipeRecord> entry : map.entrySet()) {
            Dish dish = new Dish();
            dish.id = entry.getKey();
            dish.name = entry.getValue().title;
            dish.ingredients = entry.getValue().ingredients;
            dish.cookingMethod = entry.getValue().instructions;
            list.add(dish);
        }
        return list;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Dish add(@RequestBody Dish request, @RequestHeader(value = "Authorization", required = false) String authHeader) {
        System.out.println("DishController received authHeader: " + authHeader);
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            System.out.println("Failed: authHeader is null or doesn't start with Bearer");
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing or invalid Authorization header");
        }
        String token = authHeader.substring(7);
        if (!token.equals(adminToken)) {
            System.out.println("Failed: token " + token + " does not match adminToken " + adminToken);
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid or missing token.");
        }

        if (!processingService.getIsLeader()) {
            System.out.println("Not leader, redirecting ingest to leader.");
            return consensusService.redirectIngest(request, authHeader);
        }

        String name = clean(request.name);

        if (name.length() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dish name is required.");
        }

        if (request.ingredients == null || safeList(request.ingredients).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "At least one ingredient is required.");
        }

        if (clean(request.cookingMethod).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Cooking method is required.");
        }

        synchronized (lock) {
            java.util.Map<String, RecipeRecord> data = readDishes();

            Dish dish = new Dish();
            dish.id = UUID.randomUUID().toString();
            dish.name = name;
            dish.ingredients = safeList(request.ingredients);
            dish.cookingMethod = clean(request.cookingMethod);

            RecipeRecord record = new RecipeRecord();
            record.title = dish.name;
            record.ingredients = dish.ingredients;
            record.instructions = dish.cookingMethod;
            record.picture_link = null;

            data.put(dish.id, record);
            writeDishes(data);

            // ---- add ETL-node ---
            com.example.shared.model.ETLQuery.Dish sharedDish = new com.example.shared.model.ETLQuery.Dish();
            sharedDish.setId(dish.id);
            sharedDish.setName(dish.name);
            sharedDish.setIngredients(dish.ingredients);
            sharedDish.setCookingMethod(dish.cookingMethod);

            UserRequest userRequest = new UserRequest();
            userRequest.setId(dish.id);
            userRequest.setType("INGEST");
            userRequest.setState("received");
            userRequest.setIngestDish(sharedDish);
            userRequest.setTtl(LocalDateTime.now().plusMinutes(5));

            storage.storeRequest(dish.id, userRequest);
            processingService.addToQueue(dish.id);
            storage.broadCastCopy(userRequest);
            System.out.println("Dish ingest queued with job ID: " + dish.id);
            // --- add ETL-node ----

            return dish;
        }
    }

    private void ensureDishesFile() {
        synchronized (lock) {
            if (Files.exists(dishesFile)) {
                return;
            }

            try {
                Files.createDirectories(dishesFile.getParent());
                writeDishes(new java.util.HashMap<>());
            } catch (IOException e) {
                throw new IllegalStateException("Could not create dishes file.", e);
            }
        }
    }

    private java.util.Map<String, RecipeRecord> readDishes() {
        ensureDishesFile();

        synchronized (lock) {
            try {
                String content = Files.readString(dishesFile);
                if (content.trim().isEmpty()) {
                    return new java.util.HashMap<>();
                }
                return objectMapper.readValue(content, new com.fasterxml.jackson.core.type.TypeReference<java.util.Map<String, RecipeRecord>>() {});
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not read dishes file.");
            }
        }
    }

    private void writeDishes(java.util.Map<String, RecipeRecord> data) {
        synchronized (lock) {
            try {
                objectMapper.writeValue(dishesFile.toFile(), data);
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not save dishes file.");
            }
        }
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private static List<String> safeList(List<String> value) {
        if (value == null) {
            return new ArrayList<>();
        }

        return value.stream()
                .map(DishController::clean)
                .filter(item -> !item.isEmpty())
                .toList();
    }

    public static class RecipeRecord {
        public String title;
        public List<String> ingredients = new ArrayList<>();
        public String instructions;
        public String picture_link;
    }

    public static class Dish {
        public String id;
        public String name;
        public List<String> ingredients = new ArrayList<>();
        public String cookingMethod;
    }
}