package io.companyx.ontology.prototype.graphcomparison;

import java.util.List;
import java.util.Map;
import java.util.Objects;

public record GraphAnswer(
        String id, String name, Map<String, String> details, List<String> sourceIds) {
    public GraphAnswer {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(name, "name");
        details = Map.copyOf(details);
        sourceIds = List.copyOf(sourceIds);
    }
}
