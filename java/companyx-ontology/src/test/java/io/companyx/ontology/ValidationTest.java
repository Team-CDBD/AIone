package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Path;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

final class ValidationTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private static final Path PROJECT = Path.of(
                    System.getProperty("companyx.project", System.getProperty("user.dir")))
            .toAbsolutePath()
            .normalize();
    private static Model model;
    private static CompanyXValidator validator;

    @BeforeAll
    static void buildModelAndShapes() throws IOException {
        CompanyXSourceData sourceData = new CompanyXSourceLoader().load(DATASET);
        model = new CompanyXGraphBuilder()
                .build(sourceData, PROJECT.resolve("ontology/companyx.ttl"));
        validator = new CompanyXValidator(PROJECT.resolve("ontology/shapes/companyx-shapes.ttl"));
    }

    @AfterAll
    static void closeModel() {
        model.close();
    }

    @Test
    void acceptsTheCompleteProjection() {
        CompanyXValidationResult result = validator.validate(model);

        assertTrue(result.conforms(), result.reportTurtle());
        assertEquals(0, result.violationCount());
    }

    @Test
    void detectsAMissingContractProductWithoutMutatingTheOriginalModel() {
        Model broken = ModelFactory.createDefaultModel().add(model);
        try {
            broken.removeAll(
                    CompanyXVocabulary.contract(44),
                    CompanyXVocabulary.CONTRACT_PRODUCT,
                    null);

            CompanyXValidationResult result = validator.validate(broken);

            assertFalse(result.conforms());
            assertTrue(result.violationCount() >= 1);
            assertTrue(result.reportTurtle()
                    .contains("Contract는 Product를 정확히 하나 가리켜야 한다"));
            assertTrue(model.contains(
                    CompanyXVocabulary.contract(44),
                    CompanyXVocabulary.CONTRACT_PRODUCT,
                    CompanyXVocabulary.product(7)));
        } finally {
            broken.close();
        }
    }

    @Test
    void reportsAMissingShapesFile(@TempDir Path emptyDirectory) {
        Path missing = emptyDirectory.resolve("missing-shapes.ttl");

        IOException error = assertThrows(IOException.class, () -> new CompanyXValidator(missing));

        assertTrue(error.getMessage().contains("missing-shapes.ttl"));
    }
}
