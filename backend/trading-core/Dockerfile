# Optional BuildKit named context maven-seed reuses the CI Maven repository.
# The empty stage preserves normal standalone and Compose builds.
FROM maven:3.9-eclipse-temurin-21 AS maven-seed
RUN mkdir -p /repository

FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml maven-build-retry.sh ./
RUN --mount=type=bind,from=maven-seed,source=/repository,target=/tmp/maven-seed,ro \
    mkdir -p /root/.m2/repository \
    && cp -a /tmp/maven-seed/. /root/.m2/repository/ \
    && sh maven-build-retry.sh -DskipTests dependency:go-offline
COPY src ./src
RUN sh maven-build-retry.sh -DskipTests package
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/target/trading-core-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app/app.jar"]
