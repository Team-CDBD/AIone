package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QuerySolution;
import org.apache.jena.query.ResultSet;
import org.apache.jena.rdf.model.Model;
import org.junit.jupiter.api.Test;

final class NamedGraphLearningTest {
    @Test
    void keepsTheSourceGraphBoundaryAndQueriesItsName() {
        String sourceGraphIri = CompanyXVocabulary.sourceRow("contracts", 44).getURI();
        Dataset dataset = DatasetFactory.createTxnMem();
        try {
            Model sourceGraph = dataset.getNamedModel(sourceGraphIri);
            sourceGraph.add(
                    CompanyXVocabulary.contract(44), CompanyXVocabulary.STATUS, "active");

            assertFalse(dataset.getDefaultModel()
                    .contains(
                            CompanyXVocabulary.contract(44),
                            CompanyXVocabulary.STATUS,
                            "active"));

            String query = """
                    SELECT ?source ?status
                    WHERE {
                      GRAPH ?source {
                        <%s> <%s> ?status .
                      }
                    }
                    """
                    .formatted(
                            CompanyXVocabulary.contract(44).getURI(),
                            CompanyXVocabulary.STATUS.getURI());

            try (QueryExecution execution =
                    QueryExecution.dataset(dataset).query(query).build()) {
                ResultSet results = execution.execSelect();
                assertTrue(results.hasNext());
                QuerySolution row = results.nextSolution();
                assertEquals(sourceGraphIri, row.getResource("source").getURI());
                assertEquals("active", row.getLiteral("status").getString());
                assertFalse(results.hasNext());
            }
        } finally {
            dataset.close();
        }
    }
}
