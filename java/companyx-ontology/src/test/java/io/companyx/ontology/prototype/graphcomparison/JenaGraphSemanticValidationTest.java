package io.companyx.ontology.prototype.graphcomparison;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Files;
import java.nio.file.Path;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.Resource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

final class JenaGraphSemanticValidationTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));

    @Test
    void rejectsAUsesRelationWithoutItsContractIdentity(@TempDir Path graphDirectory)
            throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode edges = JSON.readTree(graphDirectory.resolve("edges.json").toFile());
        ((ObjectNode) edges.get(136).path("properties")).remove("contract_id");
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("edges.json").toFile(), edges);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains("USES relation requires contract_id"));
    }

    @Test
    void rejectsARelationWhoseEndpointTypesContradictTheOfficialSchema(
            @TempDir Path graphDirectory) throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode edges = JSON.readTree(graphDirectory.resolve("edges.json").toFile());
        ((ObjectNode) edges.get(0)).put("source", "client_1");
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("edges.json").toFile(), edges);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains("relation endpoints must match schema"));
    }

    @Test
    void rejectsADanglingRelationEndpoint(@TempDir Path graphDirectory) throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode edges = JSON.readTree(graphDirectory.resolve("edges.json").toFile());
        ((ObjectNode) edges.get(0)).put("source", "employee_999");
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("edges.json").toFile(), edges);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains("relation endpoint must reference an existing node"));
    }

    @Test
    void rejectsADuplicateNodeSourceIdentity(@TempDir Path graphDirectory) throws Exception {
        copyOfficialGraph(graphDirectory);
        ArrayNode nodes = (ArrayNode) JSON.readTree(graphDirectory.resolve("nodes.json").toFile());
        nodes.add(nodes.get(0).deepCopy());
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("nodes.json").toFile(), nodes);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains("duplicate node source ID"));
    }

    @Test
    void rejectsAnEdgePropertyWithTheWrongDatatype(@TempDir Path graphDirectory) throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode edges = JSON.readTree(graphDirectory.resolve("edges.json").toFile());
        ((ObjectNode) edges.get(136).path("properties")).put("contract_id", "44");
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("edges.json").toFile(), edges);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains("edge property must be an integer: contract_id"));
    }

    @Test
    void rejectsANodePropertyThatCannotBeProjectedLosslessly(@TempDir Path graphDirectory)
            throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode nodes = JSON.readTree(graphDirectory.resolve("nodes.json").toFile());
        ((ObjectNode) nodes.get(0).path("properties")).putArray("aliases").add("Client-A");
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("nodes.json").toFile(), nodes);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains(
                "node property must be a scalar supported by the RDF projection: aliases"));
    }

    @Test
    void rejectsAnUnknownEdgePropertyThatCannotBeProjectedLosslessly(@TempDir Path graphDirectory)
            throws Exception {
        copyOfficialGraph(graphDirectory);
        JsonNode edges = JSON.readTree(graphDirectory.resolve("edges.json").toFile());
        ((ObjectNode) edges.get(136).path("properties")).putObject("metadata").put("revision", 1);
        JSON.writerWithDefaultPrettyPrinter()
                .writeValue(graphDirectory.resolve("edges.json").toFile(), edges);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class, () -> JenaGraphTool.load(graphDirectory));

        assertTrue(error.getMessage().contains(
                "edge property must be a scalar supported by the RDF projection: metadata"));
    }

    @Test
    void shaclRejectsAnIncorrectProjectedEdgePropertyDatatype() throws Exception {
        Model model = JenaGraphTool.loadModel(DATASET.resolve("graph"));
        try {
            Resource edge = OfficialGraphVocabulary.edge(136);
            var contractId = OfficialGraphVocabulary.property("contract_id");
            model.removeAll(edge, contractId, null);
            model.add(edge, contractId, "44");

            IllegalArgumentException error = assertThrows(
                    IllegalArgumentException.class,
                    () -> JenaOfficialGraphSemanticValidator.requireValid(model));

            assertTrue(error.getMessage().contains("DatatypeConstraintComponent"));
        } finally {
            model.close();
        }
    }

    static void copyOfficialGraph(Path graphDirectory) throws Exception {
        Path source = DATASET.resolve("graph");
        Files.copy(source.resolve("nodes.json"), graphDirectory.resolve("nodes.json"));
        Files.copy(source.resolve("edges.json"), graphDirectory.resolve("edges.json"));
    }
}
