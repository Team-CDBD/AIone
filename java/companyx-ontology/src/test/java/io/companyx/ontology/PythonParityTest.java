package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** Locks the observable results already established by the Python reference tests. */
final class PythonParityTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private static final Path PROJECT = Path.of(
                    System.getProperty("companyx.project", System.getProperty("user.dir")))
            .toAbsolutePath()
            .normalize();
    private static Model model;
    private static CompanyXQueries queries;
    private static CompanyXValidator validator;

    @BeforeAll
    static void buildLab() throws IOException {
        CompanyXSourceData sourceData = new CompanyXSourceLoader().load(DATASET);
        model = new CompanyXGraphBuilder()
                .build(sourceData, PROJECT.resolve("ontology/companyx.ttl"));
        queries = new CompanyXQueries(PROJECT.resolve("ontology/queries"));
        validator = new CompanyXValidator(PROJECT.resolve("ontology/shapes/companyx-shapes.ttl"));
    }

    @AfterAll
    static void closeModel() {
        model.close();
    }

    @Test
    void matchesThePythonProjectionAndSummaryCounts() {
        ProjectionStatistics statistics = new CompanyXStatistics().summarize(model);

        assertEquals(new ProjectionStatistics(65, 61, 120, 99, 2850), statistics);
    }

    @Test
    void matchesThePythonReferenceQueryResults() throws IOException {
        LocalDate asOf = LocalDate.of(2026, 8, 3);

        assertEquals(
                List.of(new CurrentProductResult(
                        CompanyXVocabulary.contract(44).getURI(),
                        44,
                        CompanyXVocabulary.product(7).getURI(),
                        "Product-C3",
                        LocalDate.of(2026, 3, 5),
                        LocalDate.of(2026, 10, 5))),
                queries.currentProducts(model, 1, asOf));
        assertEquals(
                List.of(new UnresolvedTicketResult(
                        CompanyXVocabulary.ticket(80).getURI(),
                        80,
                        "로그 수집 중단",
                        "in_progress",
                        "critical",
                        CompanyXVocabulary.product(10).getURI(),
                        "Product-S3")),
                queries.unresolvedTickets(model, 1));
        assertTrue(queries.unresolvedTicketsForCurrentProducts(model, 1, asOf).isEmpty());
    }

    @Test
    void matchesThePythonReferenceValidationOutcomes() {
        assertTrue(validator.validate(model).conforms());

        Model broken = ModelFactory.createDefaultModel().add(model);
        try {
            broken.removeAll(
                    CompanyXVocabulary.contract(44),
                    CompanyXVocabulary.CONTRACT_PRODUCT,
                    null);

            CompanyXValidationResult result = validator.validate(broken);
            assertFalse(result.conforms());
            assertTrue(result.reportTurtle()
                    .contains("Contract는 Product를 정확히 하나 가리켜야 한다"));
        } finally {
            broken.close();
        }
    }
}

