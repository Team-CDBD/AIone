package io.companyx.ontology.prototype.graphcomparison;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.jena.vocabulary.XSD;
import org.junit.jupiter.api.Test;

final class JenaOfficialGraphOntologyIntegrationTest {
    private static final String CX = "https://company-x.example/ontology/";
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));

    @Test
    void loadsTheSharedOntologyAndTypesOfficialGraphNodesWithItsClasses() throws Exception {
        Model model = JenaGraphTool.loadModel(DATASET.resolve("graph"));
        try {
            assertTrue(model.contains(
                    ResourceFactory.createResource(CX + "Client"), RDF.type, OWL.Class));
            assertTrue(model.contains(
                    OfficialGraphVocabulary.node("client_1"),
                    RDF.type,
                    ResourceFactory.createResource(CX + "Client")));
            assertTrue(model.contains(
                    OfficialGraphVocabulary.property("amount"), RDFS.range, XSD.integer));
            assertTrue(model.contains(
                    OfficialGraphVocabulary.property("contract_id"), RDFS.range, XSD.xlong));
            model.listObjectsOfProperty(OfficialGraphVocabulary.property("amount"))
                    .forEachRemaining(statement -> assertEquals(
                            XSD.integer.getURI(),
                            statement.asLiteral().getDatatypeURI()));
            assertTrue(!model.contains(
                    OfficialGraphVocabulary.property("amount"),
                    RDFS.domain,
                    ResourceFactory.createResource(CX + "Contract")));
            assertTrue(!model.contains(
                    OfficialGraphVocabulary.property("priority"),
                    RDFS.domain,
                    ResourceFactory.createResource(CX + "SupportTicket")));
        } finally {
            model.close();
        }
    }
}
