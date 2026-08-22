package io.companyx.ontology.prototype.graphcomparison;

import java.util.Objects;

public record GraphQuery(GraphQuestion question) {
    public GraphQuery {
        Objects.requireNonNull(question, "question");
    }
}
