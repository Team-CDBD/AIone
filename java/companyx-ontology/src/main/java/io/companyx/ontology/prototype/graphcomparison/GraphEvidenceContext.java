package io.companyx.ontology.prototype.graphcomparison;

/** Identifies the source role of graph-tool answers and evidence. */
public enum GraphEvidenceContext {
    OFFICIAL_JSON_RDF_PROJECTION("rdf_projection", "official_json_graph_view");

    private final String answerDataRole;
    private final String evidenceRole;

    GraphEvidenceContext(String answerDataRole, String evidenceRole) {
        this.answerDataRole = answerDataRole;
        this.evidenceRole = evidenceRole;
    }

    public String answerDataRole() {
        return answerDataRole;
    }

    public String evidenceRole() {
        return evidenceRole;
    }
}
