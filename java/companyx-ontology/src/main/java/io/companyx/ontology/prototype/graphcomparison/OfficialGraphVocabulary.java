package io.companyx.ontology.prototype.graphcomparison;

import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.ResourceFactory;

final class OfficialGraphVocabulary {
    static final String CX = "https://company-x.example/ontology/";
    static final String RES = "https://company-x.example/resource/official-graph/";

    static final Resource GRAPH_EDGE = resource("GraphEdge");
    static final Property SOURCE_ID = property("sourceId");
    static final Property SOURCE_LOCATOR = property("sourceLocator");
    static final Property EDGE_SOURCE = property("edgeSource");
    static final Property EDGE_TARGET = property("edgeTarget");
    static final Property EDGE_RELATION = property("edgeRelation");

    private OfficialGraphVocabulary() {}

    static Resource node(String sourceId) {
        return ResourceFactory.createResource(RES + "node/" + sourceId);
    }

    static Resource edge(int index) {
        return ResourceFactory.createResource(RES + "edge/" + index);
    }

    static Resource type(String sourceType) {
        return switch (sourceType) {
            case "client" -> resource("Client");
            case "product" -> resource("Product");
            case "employee" -> resource("Employee");
            case "project" -> resource("Project");
            case "department" -> resource("Department");
            default -> throw new IllegalArgumentException("unsupported official graph type: " + sourceType);
        };
    }

    static Property property(String localName) {
        return ResourceFactory.createProperty(CX, localName);
    }

    private static Resource resource(String localName) {
        return ResourceFactory.createResource(CX + localName);
    }
}
