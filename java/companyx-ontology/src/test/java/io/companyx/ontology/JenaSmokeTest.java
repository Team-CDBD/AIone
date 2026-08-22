package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.junit.jupiter.api.Test;

final class JenaSmokeTest {
    @Test
    void createsAnInMemoryRdfModelOnJava21() {
        Model model = ModelFactory.createDefaultModel();
        model.createResource("https://company-x.example/resource/client/1")
                .addProperty(
                        model.createProperty("https://company-x.example/ontology/name"),
                        "Client-A");

        // ADR-0010: Jena 6.1.0이 실제로 JDK21 바이트코드를 요구해 25에서 21로 낮췄다(원격 실빌드로 확인).
        assertEquals(21, Runtime.version().feature());
        assertTrue(model.containsResource(
                model.createResource("https://company-x.example/resource/client/1")));
        assertEquals(1, model.size());
    }
}

