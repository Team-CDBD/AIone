package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;
import org.apache.jena.rdf.model.Model;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

final class QueryTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private static final Path PROJECT = Path.of(
                    System.getProperty("companyx.project", System.getProperty("user.dir")))
            .toAbsolutePath()
            .normalize();
    private static Model model;
    private static CompanyXQueries queries;

    @BeforeAll
    static void buildModel() throws IOException {
        CompanyXSourceData sourceData = new CompanyXSourceLoader().load(DATASET);
        model = new CompanyXGraphBuilder()
                .build(sourceData, PROJECT.resolve("ontology/companyx.ttl"));
        queries = new CompanyXQueries(PROJECT.resolve("ontology/queries"));
    }

    @AfterAll
    static void closeModel() {
        model.close();
    }

    @Test
    void findsClientAsCurrentProductAtTheReferenceDate() throws IOException {
        List<CurrentProductResult> results =
                queries.currentProducts(model, 1, LocalDate.of(2026, 8, 3));

        assertEquals(1, results.size());
        CurrentProductResult result = results.getFirst();
        assertEquals(44, result.contractId());
        assertEquals(CompanyXVocabulary.contract(44).getURI(), result.contractIri());
        assertEquals(CompanyXVocabulary.product(7).getURI(), result.productIri());
        assertEquals("Product-C3", result.productName());
        assertEquals(LocalDate.of(2026, 3, 5), result.startDate());
        assertEquals(LocalDate.of(2026, 10, 5), result.endDate());
    }

    @Test
    void treatsTheContractEndDateAsInclusive() throws IOException {
        List<CurrentProductResult> results =
                queries.currentProducts(model, 1, LocalDate.of(2025, 9, 26));

        assertEquals(1, results.size());
        assertEquals(57, results.getFirst().contractId());
        assertEquals("Product-S1", results.getFirst().productName());
    }

    @Test
    void findsClientAsUnresolvedTicketWithoutCallingItACurrentProductIssue()
            throws IOException {
        List<UnresolvedTicketResult> unresolved = queries.unresolvedTickets(model, 1);
        List<CurrentProductTicketResult> currentProductIssues =
                queries.unresolvedTicketsForCurrentProducts(
                        model, 1, LocalDate.of(2026, 8, 3));

        assertEquals(1, unresolved.size());
        UnresolvedTicketResult ticket = unresolved.getFirst();
        assertEquals(80, ticket.ticketId());
        assertEquals("로그 수집 중단", ticket.title());
        assertEquals("in_progress", ticket.status());
        assertEquals("critical", ticket.priority());
        assertEquals(CompanyXVocabulary.product(10).getURI(), ticket.productIri());
        assertEquals("Product-S3", ticket.productName());
        assertTrue(currentProductIssues.isEmpty());
    }
}

