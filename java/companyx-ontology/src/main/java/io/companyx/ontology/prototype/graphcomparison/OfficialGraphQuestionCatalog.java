package io.companyx.ontology.prototype.graphcomparison;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;

/** Validates that the submitted questions file exposes exactly the supported graph questions. */
final class OfficialGraphQuestionCatalog {
    private static final ObjectMapper JSON = new ObjectMapper();

    private OfficialGraphQuestionCatalog() {}

    static GraphQuestion resolve(Path datasetDirectory, String questionText) throws IOException {
        requireValid(datasetDirectory);
        return GraphQuestion.fromText(questionText);
    }

    static void requireValid(Path datasetDirectory) throws IOException {
        JsonNode questions = JSON.readTree(datasetDirectory.resolve("questions.json").toFile());
        if (!questions.isArray()) {
            throw new IllegalArgumentException("questions.json must contain an array");
        }

        Set<GraphQuestion> discovered = new HashSet<>();
        for (JsonNode entry : questions) {
            if (!"knowledge_graph".equals(entry.path("tool").textValue())) {
                continue;
            }
            JsonNode questionNode = entry.path("q");
            if (!questionNode.isTextual() || questionNode.textValue().isBlank()) {
                throw new IllegalArgumentException("knowledge graph question must be non-blank text");
            }
            GraphQuestion question = GraphQuestion.fromText(questionNode.textValue());
            if (!discovered.add(question)) {
                throw new IllegalArgumentException("duplicate knowledge graph question: " + question.text());
            }
        }
        if (discovered.size() != GraphQuestion.values().length
                || !discovered.containsAll(Set.of(GraphQuestion.values()))) {
                throw new IllegalArgumentException(
                    "questions.json must contain exactly the supported knowledge graph questions");
        }
    }
}
