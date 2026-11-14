# Shared Models

This directory contains the `shared-models` Java library. 

## Purpose
In a distributed microservices architecture, multiple nodes often need to communicate using the same data structures (Data Transfer Objects). Instead of duplicating classes like `RecipeQuery`, `RecipeDocument`, or `SearchResponse` in `coordinator`, `recipe-node`, and `llm-node`, they are centralized here.

## Contents
- **DTOs (Data Transfer Objects)**: Standardized objects for cross-node HTTP communication.
- **Enums**: Shared enumerations like `TaskState`.

## How it works
This library is built as a standard Maven JAR (`mvn clean install`).
The other Spring Boot nodes (`coordinator`, `recipe-node`, etc.) declare this module as a dependency in their `pom.xml`:

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>shared-models</artifactId>
    <version>1.0.0</version>
</dependency>
```

When building the project via Docker, the parent `pom.xml` ensures that `shared-models` is built first before any dependent microservices are compiled.
