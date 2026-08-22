package io.companyx.ontology.prototype.graphcomparison;

import java.util.List;
import java.util.Objects;

public record GraphOperationResult(
        String engine,
        String queryLanguage,
        String executedQuery,
        List<GraphAnswer> answers,
        List<String> warnings,
        GraphEvidenceContext evidenceContext) {
    public GraphOperationResult(
            String engine,
            String queryLanguage,
            String executedQuery,
            List<GraphAnswer> answers,
            List<String> warnings) {
        this(
                engine,
                queryLanguage,
                executedQuery,
                answers,
                warnings,
                GraphEvidenceContext.OFFICIAL_JSON_RDF_PROJECTION);
    }

    public GraphOperationResult {
        Objects.requireNonNull(engine, "engine");
        Objects.requireNonNull(queryLanguage, "queryLanguage");
        Objects.requireNonNull(executedQuery, "executedQuery");
        Objects.requireNonNull(evidenceContext, "evidenceContext");
        answers = List.copyOf(answers);
        warnings = List.copyOf(warnings);
    }
}
