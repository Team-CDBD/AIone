package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

final class OntologyLabCliTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private static final Path PROJECT = Path.of(
                    System.getProperty("companyx.project", System.getProperty("user.dir")))
            .toAbsolutePath()
            .normalize();

    @Test
    void runsTheCompleteJenaLearningFlow() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (PrintStream output = new PrintStream(bytes, true, StandardCharsets.UTF_8)) {
            new OntologyLabCli().run(
                    new String[] {"all", "--client-id", "1", "--as-of", "2026-08-03"},
                    output,
                    DATASET,
                    PROJECT);
        }

        String result = bytes.toString(StandardCharsets.UTF_8);
        assertTrue(result.contains("[1] TBox"));
        assertTrue(result.contains("Contract instance : 65건"));
        assertTrue(result.contains("전체 RDF triple   : 2850개"));
        assertTrue(result.contains("Contract 44: Product-C3"));
        assertTrue(result.contains("Ticket 80: 로그 수집 중단 / Product-S3"));
        assertTrue(result.contains("[SHACL 정상 그래프]"));
        assertTrue(result.contains("violations: 0"));
        assertTrue(result.contains("[의도적으로 망가뜨린 그래프]"));
        assertTrue(result.contains("conforms: false"));
    }

    @Test
    void rejectsAnUnknownCommandBeforeLoadingData() {
        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> new OntologyLabCli()
                        .run(new String[] {"unknown"}, System.out, DATASET, PROJECT));

        assertEquals(
                "명령이 필요합니다: inspect|stats|query|validate|break-it|all",
                error.getMessage());
    }
}

