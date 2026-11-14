package com.example.shared.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class LLMRequest {
    private String userQuery;

    public LLMRequest() {}

    public String getUserQuery() { return userQuery;}
    public void setUserQuery(String userQuery) { this.userQuery = userQuery;}
}