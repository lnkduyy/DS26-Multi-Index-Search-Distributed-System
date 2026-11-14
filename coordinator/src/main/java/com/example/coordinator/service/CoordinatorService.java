package com.example.coordinator.service;

import java.time.LocalDateTime;
import java.util.UUID;

import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.example.coordinator.model.UserRequest;
import com.example.shared.model.LLMRequest;


@Service
public class CoordinatorService {

    private final RestTemplate restTemplate;
    private final ProcessingService processingService;
    private final RequestStorage storage;
    private final ConsensusService consensus;
    
    public CoordinatorService(RestTemplate restTemplate, 
            RequestStorage storage, ProcessingService processingService, ConsensusService consensus) {
        this.restTemplate = restTemplate;
        this.processingService = processingService;
        this.storage = storage;
        this.consensus = consensus;
    }

    public String search(LLMRequest request) { 
        if (processingService.getIsLeader()) {
            String id = UUID.randomUUID().toString(); 
            System.out.println("User Query: " + request.getUserQuery());

            UserRequest userRequest = new UserRequest();
            userRequest.setId(id);
            userRequest.setState("received");
            userRequest.setUserQuery(request.getUserQuery());
            
            userRequest.setTtl(LocalDateTime.now().plusSeconds(300));

            processingService.addToQueue(id);
            storage.storeRequest(id, userRequest);
            storage.broadCastCopy(userRequest);

            return id;
        } else {
            return consensus.redirect(request);
        }
    }

    public ResponseEntity<com.example.shared.model.SearchResponse> get(String id) {
        UserRequest request = storage.getRequest(id);
        if (request == null) {
            return ResponseEntity.notFound().build();
        }
        
        com.example.shared.model.SearchResponse response = new com.example.shared.model.SearchResponse();
        if ("done".equals(request.getState())) {
            response.setState(com.example.shared.model.StatusState.SUCCESS);
            response.setAnswer(request.getResult());
            response.setRecipes(request.getRecipeQueryResults());
        } else if ("error".equals(request.getState())) {
            response.setState(com.example.shared.model.StatusState.FAILED);
        } else if ("quota_exceeded".equals(request.getState())) {
            response.setState(com.example.shared.model.StatusState.QUOTA_EXCEEDED);
        } else if ("received".equals(request.getState())) {
            response.setState(com.example.shared.model.StatusState.RECEIVED);
        } else {
            response.setState(com.example.shared.model.StatusState.PENDING);
        }
        return ResponseEntity.ok(response);
    }

    public UserRequest getTest(String id) {
        return storage.getRequest(id); 
    }
}