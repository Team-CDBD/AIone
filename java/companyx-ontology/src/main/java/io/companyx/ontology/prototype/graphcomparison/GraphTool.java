package io.companyx.ontology.prototype.graphcomparison;

public interface GraphTool extends AutoCloseable {
    GraphOperationResult query(GraphQuery query) throws Exception;

    @Override
    void close() throws Exception;
}
