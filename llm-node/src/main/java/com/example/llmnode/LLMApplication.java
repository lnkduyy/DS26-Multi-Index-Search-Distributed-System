package com.example.llmnode;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class LLMApplication {

    public static void main(String[] args) {
        SpringApplication.run(LLMApplication.class, args);
    }
}  

// mvn -pl llm-node spring-boot:run