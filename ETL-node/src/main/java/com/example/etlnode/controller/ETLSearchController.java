package com.example.etlnode.controller;

import com.example.etlnode.model.ETLModels.IngestRequest;
import com.example.etlnode.model.ETLModels.IngestResponse;
import com.example.shared.model.ETLQuery;
import com.example.shared.model.ETLQueryResult;
import com.example.etlnode.service.ETLService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/etl")
public class ETLSearchController {

    private final ETLService etlService;

    public ETLSearchController(ETLService etlService) {
        this.etlService = etlService;
    }

    // ── New: ingest dishes endpoint ────────────────────────────────────────────

    /**
     * POST /etl/ingest
     *
     * Accepts a list of dishes and forwards them to the Python FastAPI
     * ingest service, which enriches and uploads them to Qdrant.
     *
     * Returns 202 Accepted immediately — Qdrant upload is async.
     *
     * Request body (matches dishes.json):
     * {
     *   "dishes": [
     *     {
     *       "id": "optional-uuid",
     *       "name": "Egg Fried Rice",
     *       "ingredients": ["Rice", "Egg", "Soy sauce"],
     *       "cookingMethod": "Fry rice with egg and soy sauce"
     *     }
     *   ]
     * }
     */
    @PostMapping(value = "/ingest", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<IngestResponse> ingest(@RequestBody IngestRequest request) {
        if (request.dishes == null || request.dishes.isEmpty()) {
            return ResponseEntity.badRequest().build();
        }
        IngestResponse response = etlService.ingest(request);
        return ResponseEntity.accepted().body(response);   // 202
    }

    @PostMapping(value = "/process", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ETLQueryResult> process(@RequestBody ETLQuery query) {
        if (query.getDishes() == null || query.getDishes().isEmpty()) {
            return ResponseEntity.badRequest().build();
        }
        ETLQueryResult response = etlService.process(query);
        return ResponseEntity.ok(response);
    }
}