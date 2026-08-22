package io.companyx.ontology.prototype.graphcomparison;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.util.Map;
import org.apache.jena.rdf.model.Literal;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.RDFNode;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

final class JenaOfficialGraphProjectionParityTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));

    @Test
    void preservesEveryOfficialNodeAndEdgeIdentityLocatorAndProperty() throws Exception {
        JsonNode nodes = JSON.readTree(DATASET.resolve("graph/nodes.json").toFile());
        JsonNode edges = JSON.readTree(DATASET.resolve("graph/edges.json").toFile());

        assertEquals(133, nodes.size());
        assertEquals(354, edges.size());
        Model model = JenaGraphTool.loadModel(DATASET.resolve("graph"));
        try {
            assertEquals(133, model.listResourcesWithProperty(OfficialGraphVocabulary.SOURCE_ID).toList().size());
            assertEquals(
                    354,
                    model.listResourcesWithProperty(RDF.type, OfficialGraphVocabulary.GRAPH_EDGE)
                            .toList()
                            .size());

            for (JsonNode node : nodes) {
                String id = node.required("id").textValue();
                Resource resource = OfficialGraphVocabulary.node(id);
                assertTrue(model.contains(resource, RDF.type,
                        OfficialGraphVocabulary.type(node.required("type").textValue())));
                assertTrue(model.contains(resource, OfficialGraphVocabulary.SOURCE_ID, id));
                assertTrue(model.contains(
                        resource,
                        OfficialGraphVocabulary.SOURCE_LOCATOR,
                        "graph/nodes.json#" + id));
                assertTrue(model.contains(resource, RDFS.label, node.required("name").textValue()));
                assertProperties(model, resource, node.path("properties"));
                assertEquals(
                        4 + node.path("properties").size(),
                        model.listStatements(resource, null, (RDFNode) null).toList().size());
            }

            for (int index = 0; index < edges.size(); index++) {
                JsonNode edge = edges.get(index);
                Resource resource = OfficialGraphVocabulary.edge(index);
                assertTrue(model.contains(resource, RDF.type, OfficialGraphVocabulary.GRAPH_EDGE));
                assertTrue(model.contains(
                        resource,
                        OfficialGraphVocabulary.EDGE_SOURCE,
                        OfficialGraphVocabulary.node(edge.required("source").textValue())));
                assertTrue(model.contains(
                        resource,
                        OfficialGraphVocabulary.EDGE_TARGET,
                        OfficialGraphVocabulary.node(edge.required("target").textValue())));
                assertTrue(model.contains(
                        resource,
                        OfficialGraphVocabulary.EDGE_RELATION,
                        edge.required("relation").textValue()));
                assertTrue(model.contains(
                        resource,
                        OfficialGraphVocabulary.SOURCE_LOCATOR,
                        "graph/edges.json#index=" + index));
                assertProperties(model, resource, edge.path("properties"));
                assertEquals(
                        5 + edge.path("properties").size(),
                        model.listStatements(resource, null, (RDFNode) null).toList().size());
            }
        } finally {
            model.close();
        }
    }

    private static void assertProperties(Model model, Resource resource, JsonNode properties) {
        for (Map.Entry<String, JsonNode> property : properties.properties()) {
            assertTrue(model.contains(
                    resource,
                    OfficialGraphVocabulary.property(property.getKey()),
                    rdfValue(model, property.getValue())));
        }
    }

    private static RDFNode rdfValue(Model model, JsonNode value) {
        if (value.isTextual()) {
            return model.createLiteral(value.textValue());
        }
        if (value.isIntegralNumber()) {
            return model.createTypedLiteral(value.longValue());
        }
        if (value.isFloatingPointNumber()) {
            return model.createTypedLiteral(value.doubleValue());
        }
        if (value.isBoolean()) {
            return model.createTypedLiteral(value.booleanValue());
        }
        throw new IllegalArgumentException("Unsupported official graph property value: " + value);
    }
}
