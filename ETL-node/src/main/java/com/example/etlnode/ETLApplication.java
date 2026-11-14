package com.example.etlnode;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ETLApplication {

    public static void main(String[] args) {
        SpringApplication.run(ETLApplication.class, args);
    }
}  

// mvn -pl llm-node spring-boot:run