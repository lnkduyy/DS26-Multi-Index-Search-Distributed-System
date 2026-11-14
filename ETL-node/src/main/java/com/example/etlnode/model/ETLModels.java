package com.example.etlnode.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

// ── Ingest request — matches dishes.json structure ────────────────────────────

public class ETLModels {

    public static class Dish {
        public String id;
        public String name;
        public List<String> ingredients;
        public String cookingMethod;
    }

    public static class IngestRequest {
        public List<Dish> dishes;
    }

    // ── Generic response wrapper ───────────────────────────────────────────────

    public static class IngestResponse {
        public String status;
        public int queued;
        public List<String> ids;
        public String message;
    }
}