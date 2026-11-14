FROM maven:3.9.4-eclipse-temurin-17 AS build
WORKDIR /app
COPY . .
RUN mvn -pl shared-models,llm-node clean install -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/llm-node/target/llm-node-*.jar app.jar
EXPOSE 8120
ENTRYPOINT ["java", "-jar", "app.jar"]
