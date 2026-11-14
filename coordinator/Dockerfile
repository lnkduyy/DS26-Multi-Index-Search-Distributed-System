FROM maven:3.9.4-eclipse-temurin-17 AS build
WORKDIR /app
# Copy the root pom and modules
COPY . .
# Build the coordinator (and its dependent shared-models)
RUN mvn -pl shared-models,coordinator clean install -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/coordinator/target/coordinator-*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
