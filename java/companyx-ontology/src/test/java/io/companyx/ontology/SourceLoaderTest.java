package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

final class SourceLoaderTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private final CompanyXSourceLoader loader = new CompanyXSourceLoader();

    @Test
    void loadsTheExpectedReadOnlySourceBaseline() throws IOException {
        CompanyXSourceData data = loader.load(DATASET);

        assertEquals(30, data.clients().size());
        assertEquals(12, data.products().size());
        assertEquals(65, data.contracts().size());
        assertEquals(120, data.supportTickets().size());
        assertEquals(DATASET.toAbsolutePath().normalize(), data.datasetDirectory());
    }

    @Test
    void preservesTheRowsNeededForTheFirstLearningQuestion() throws IOException {
        CompanyXSourceData data = loader.load(DATASET);

        ClientRow client = client(data, 1);
        assertEquals("Client-A", client.name());
        assertEquals(LocalDate.of(2023, 2, 19), client.registeredAt());

        assertEquals("Product-S1", product(data, 3).name());
        assertEquals("Product-C3", product(data, 7).name());

        ContractRow contract44 = contract(data, 44);
        assertEquals(1, contract44.clientId());
        assertEquals(7, contract44.productId());
        assertEquals(LocalDate.of(2026, 3, 5), contract44.startDate());
        assertEquals(LocalDate.of(2026, 10, 5), contract44.endDate());
        assertEquals("active", contract44.status());

        ContractRow contract57 = contract(data, 57);
        assertEquals(3, contract57.productId());
        assertEquals(LocalDate.of(2024, 11, 26), contract57.startDate());
        assertEquals(LocalDate.of(2025, 9, 26), contract57.endDate());

        SupportTicketRow ticket80 = ticket(data, 80);
        assertEquals(1, ticket80.clientId());
        assertEquals(10, ticket80.productId());
        assertEquals("로그 수집 중단", ticket80.title());
        assertEquals("critical", ticket80.priority());
        assertEquals("in_progress", ticket80.status());
        assertEquals(LocalDateTime.of(2025, 6, 11, 9, 39, 12), ticket80.createdAt());
        assertNull(ticket80.resolvedAt());
    }

    @Test
    void keepsCommasInsideQuotedSourceText() throws IOException {
        ProductRow product = product(loader.load(DATASET), 1);

        assertTrue(product.description().contains("플랫폼. 멀티클라우드"));
    }

    @Test
    void reportsTheMissingSourcePath(@TempDir Path emptyDirectory) {
        IOException error = assertThrows(IOException.class, () -> loader.load(emptyDirectory));

        assertTrue(error.getMessage().contains("sql/02-data.sql"));
    }

    private static ClientRow client(CompanyXSourceData data, int id) {
        return data.clients().stream()
                .filter(row -> row.id() == id)
                .findFirst()
                .orElseThrow();
    }

    private static ProductRow product(CompanyXSourceData data, int id) {
        return data.products().stream()
                .filter(row -> row.id() == id)
                .findFirst()
                .orElseThrow();
    }

    private static ContractRow contract(CompanyXSourceData data, int id) {
        return data.contracts().stream()
                .filter(row -> row.id() == id)
                .findFirst()
                .orElseThrow();
    }

    private static SupportTicketRow ticket(CompanyXSourceData data, int id) {
        return data.supportTickets().stream()
                .filter(row -> row.id() == id)
                .findFirst()
                .orElseThrow();
    }
}

