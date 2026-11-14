package com.example.llmnode.controller;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.llmnode.service.LLMService;
import com.fasterxml.jackson.databind.JsonNode;
import com.example.shared.model.LLMRequest;

@RestController
@RequestMapping("/llm")
public class LLMController {
    private final LLMService llmService;

    public LLMController(LLMService llmService) {
        this.llmService = llmService;
    }

    @PostMapping(value = "/decompose", produces = MediaType.APPLICATION_JSON_VALUE)
    public String decompose(@RequestBody LLMRequest request) {
        return llmService.decompose(request);
    }

    @PostMapping(value = "/answer", produces = MediaType.APPLICATION_JSON_VALUE)
    public String answer(@RequestBody JsonNode request) {
        return llmService.answer(request);
    }
}