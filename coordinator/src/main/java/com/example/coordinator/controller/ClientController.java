package com.example.coordinator.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.coordinator.model.UserRequest;
import com.example.coordinator.service.CoordinatorService;
import com.example.shared.model.LLMRequest;
import com.example.shared.model.SearchResponse;

@RestController
@RequestMapping("/")
public class ClientController {

    private final CoordinatorService coordinatorService;

    public ClientController(CoordinatorService coordinatorService) {
        this.coordinatorService = coordinatorService;
    }

    @PostMapping("/search")
    public String search(@RequestBody LLMRequest request) {
        return coordinatorService.search(request);
    }

    @GetMapping("/get")
    public ResponseEntity<SearchResponse> get(@RequestParam String id) {
        return coordinatorService.get(id);
    } 

    @GetMapping("/gettest") // just for test
    public UserRequest getTest(@RequestParam String id) {
        return coordinatorService.getTest(id);
    }
}
