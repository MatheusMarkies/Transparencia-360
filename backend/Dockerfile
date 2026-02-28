FROM eclipse-temurin:17-jdk-alpine
VOLUME /tmp
WORKDIR /app
COPY . .
# We use dos2unix or run sh directly to avoid Windows CRLF issues
RUN chmod +x ./gradlew
# Build the jar skipping tests
RUN ./gradlew clean build -x test --no-daemon

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "build/libs/core-0.0.1-SNAPSHOT.jar"]
