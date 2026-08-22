package io.companyx.ontology;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Set;
import java.util.stream.Collectors;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

final class GraphProjectionTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));
    private static final Path PROJECT = Path.of(
                    System.getProperty("companyx.project", System.getProperty("user.dir")))
            .toAbsolutePath()
            .normalize();
    private static CompanyXSourceData sourceData;
    private static Model model;

    @BeforeAll
    static void buildModel() throws IOException {
        sourceData = new CompanyXSourceLoader().load(DATASET);
        model = new CompanyXGraphBuilder()
                .build(sourceData, PROJECT.resolve("ontology/companyx.ttl"));
    }

    @AfterAll
    static void closeModel() {
        if (model != null) {
            model.close();
        }
    }

    @Test
    void loadsTheSharedProjectOntologyBeforeAddingInstances() {
        assertTrue(model.contains(CompanyXVocabulary.CONTRACT, RDF.type, OWL.Class));
        assertTrue(model.contains(
                CompanyXVocabulary.CONTRACT_PRODUCT,
                RDFS.domain,
                CompanyXVocabulary.CONTRACT));
    }

    @Test
    void projectsEveryBusinessRecordAsAnIdentityBearingResource() {
        assertEquals(
                65,
                model.listResourcesWithProperty(RDF.type, CompanyXVocabulary.CONTRACT)
                        .toSet()
                        .size());
        assertEquals(
                120,
                model.listResourcesWithProperty(RDF.type, CompanyXVocabulary.SUPPORT_TICKET)
                        .toSet()
                        .size());
    }

    @Test
    void projectsExactlyTheSourceContractIdentities() {
        Set<Resource> expectedContracts = sourceData.contracts().stream()
                .map(row -> CompanyXVocabulary.contract(row.id()))
                .collect(Collectors.toUnmodifiableSet());
        Set<Resource> projectedContracts = model
                .listResourcesWithProperty(RDF.type, CompanyXVocabulary.CONTRACT)
                .toSet();

        assertEquals(expectedContracts, projectedContracts);
    }

    @Test
    void projectsEachContractToItsSourceProduct() {
        sourceData.contracts().forEach(row -> assertTrue(model.contains(
                CompanyXVocabulary.contract(row.id()),
                CompanyXVocabulary.CONTRACT_PRODUCT,
                CompanyXVocabulary.product(row.productId())),
                () -> "Contract %d의 product_id=%d 투영이 다릅니다."
                        .formatted(row.id(), row.productId())));
    }

    @Test
    void projectsContract44WithIdentityTimeAndProvenance() {
        Resource contract = CompanyXVocabulary.contract(44);
        Resource source = CompanyXVocabulary.sourceRow("contracts", 44);

        assertTrue(model.contains(contract, RDF.type, CompanyXVocabulary.CONTRACT));
        assertTrue(model.contains(
                contract,
                CompanyXVocabulary.RECORD_ID,
                model.createTypedLiteral("44", XSDDatatype.XSDinteger)));
        assertTrue(model.contains(
                contract, CompanyXVocabulary.CONTRACT_CLIENT, CompanyXVocabulary.client(1)));
        assertTrue(model.contains(
                contract, CompanyXVocabulary.CONTRACT_PRODUCT, CompanyXVocabulary.product(7)));
        assertTrue(model.contains(
                contract,
                CompanyXVocabulary.START_DATE,
                model.createTypedLiteral("2026-03-05", XSDDatatype.XSDdate)));
        assertTrue(model.contains(
                contract,
                CompanyXVocabulary.END_DATE,
                model.createTypedLiteral("2026-10-05", XSDDatatype.XSDdate)));
        assertTrue(model.contains(contract, CompanyXVocabulary.STATUS, "active"));
        assertTrue(model.contains(contract, CompanyXVocabulary.WAS_DERIVED_FROM, source));
        assertTrue(model.contains(
                source, CompanyXVocabulary.SOURCE_LOCATOR, "sql/contracts#id=44"));
    }

    @Test
    void keepsTicket80SeparateFromItsClientAndProduct() {
        Resource ticket = CompanyXVocabulary.ticket(80);

        assertTrue(model.contains(
                ticket, CompanyXVocabulary.TICKET_CLIENT, CompanyXVocabulary.client(1)));
        assertTrue(model.contains(
                ticket, CompanyXVocabulary.TICKET_PRODUCT, CompanyXVocabulary.product(10)));
        assertTrue(model.contains(
                ticket,
                CompanyXVocabulary.CREATED_AT,
                model.createTypedLiteral("2025-06-11T09:39:12", XSDDatatype.XSDdateTime)));
        assertFalse(model.contains(ticket, CompanyXVocabulary.RESOLVED_AT));
        assertTrue(model.contains(
                ticket,
                CompanyXVocabulary.WAS_DERIVED_FROM,
                CompanyXVocabulary.sourceRow("support_tickets", 80)));
    }
}
