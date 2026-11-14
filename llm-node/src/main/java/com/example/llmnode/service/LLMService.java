package com.example.llmnode.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.example.shared.model.LLMRequest;

@Service
public class LLMService {
    private final RestTemplate restTemplate;
    private final String pythonApiBaseUrl;

    public LLMService(
            RestTemplate restTemplate,
            @Value("${python.llm.api.base-url:http://127.0.0.1:5000}") String pythonApiBaseUrl) {
        this.restTemplate = restTemplate;
        this.pythonApiBaseUrl = pythonApiBaseUrl;
    }

    public String decompose(LLMRequest request) {
        return postJson("/decompose", request);
    }

    public String answer(JsonNode request) {
        return postJson("/answer", request);
    }

    private String postJson(String path, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Object> entity = new HttpEntity<>(body, headers);
        return restTemplate.postForObject(pythonApiBaseUrl + path, entity, String.class);
    }
}