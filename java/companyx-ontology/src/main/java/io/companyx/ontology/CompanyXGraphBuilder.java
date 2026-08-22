package io.companyx.ontology;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.rdf.model.Literal;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

public final class CompanyXGraphBuilder {
    private static final DateTimeFormatter XSD_DATE_TIME =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    /**
     * Loads the project ontology and projects source records into an in-memory RDF model.
     * Source rows remain authoritative; every projected business record links back to its
     * table-and-primary-key provenance resource.
     */
    public Model build(CompanyXSourceData sourceData, Path ontologyPath) throws IOException {
        Path normalizedOntology = ontologyPath.toAbsolutePath().normalize();
        if (!Files.isRegularFile(normalizedOntology)) {
            throw new IOException("Company-X ontology를 찾지 못했습니다: " + normalizedOntology);
        }

        Model model = ModelFactory.createDefaultModel();
        try (InputStream input = Files.newInputStream(normalizedOntology)) {
            RDFDataMgr.read(model, input, Lang.TURTLE);
        } catch (RuntimeException | IOException error) {
            model.close();
            throw error;
        }

        model.setNsPrefix("cx", CompanyXVocabulary.CX_NS);
        model.setNsPrefix("res", CompanyXVocabulary.RESOURCE_NS);
        model.setNsPrefix("prov", CompanyXVocabulary.PROV_NS);

        sourceData.clients().forEach(row -> addClient(model, row));
        sourceData.products().forEach(row -> addProduct(model, row));
        sourceData.contracts().forEach(row -> addContract(model, row));
        sourceData.supportTickets().forEach(row -> addSupportTicket(model, row));
        return model;
    }

    private static void addClient(Model model, ClientRow row) {
        model.add(CompanyXVocabulary.client(row.id()), RDF.type, CompanyXVocabulary.CLIENT);
        model.add(
                CompanyXVocabulary.client(row.id()),
                RDFS.label,
                model.createLiteral(row.name()));
    }

    private static void addProduct(Model model, ProductRow row) {
        model.add(CompanyXVocabulary.product(row.id()), RDF.type, CompanyXVocabulary.PRODUCT);
        model.add(
                CompanyXVocabulary.product(row.id()),
                RDFS.label,
                model.createLiteral(row.name()));
    }

    private static void addContract(Model model, ContractRow row) {
        Resource contract = CompanyXVocabulary.contract(row.id());
        Resource client = CompanyXVocabulary.client(row.clientId());
        Resource product = CompanyXVocabulary.product(row.productId());
        Resource source = addSourceRow(model, "contracts", row.id());

        model.add(contract, RDF.type, CompanyXVocabulary.CONTRACT);
        model.add(contract, CompanyXVocabulary.RECORD_ID, integer(model, row.id()));
        model.add(contract, CompanyXVocabulary.CONTRACT_CLIENT, client);
        model.add(contract, CompanyXVocabulary.CONTRACT_PRODUCT, product);
        model.add(contract, CompanyXVocabulary.START_DATE, date(model, row.startDate()));
        model.add(contract, CompanyXVocabulary.STATUS, row.status());
        model.add(contract, CompanyXVocabulary.AMOUNT, integer(model, row.amount()));
        model.add(contract, CompanyXVocabulary.WAS_DERIVED_FROM, source);
        model.add(client, CompanyXVocabulary.HAS_CONTRACT, contract);
        if (row.endDate() != null) {
            model.add(contract, CompanyXVocabulary.END_DATE, date(model, row.endDate()));
        }
    }

    private static void addSupportTicket(Model model, SupportTicketRow row) {
        Resource ticket = CompanyXVocabulary.ticket(row.id());
        Resource client = CompanyXVocabulary.client(row.clientId());
        Resource product = CompanyXVocabulary.product(row.productId());
        Resource source = addSourceRow(model, "support_tickets", row.id());

        model.add(ticket, RDF.type, CompanyXVocabulary.SUPPORT_TICKET);
        model.add(ticket, RDFS.label, row.title());
        model.add(ticket, CompanyXVocabulary.RECORD_ID, integer(model, row.id()));
        model.add(ticket, CompanyXVocabulary.TICKET_CLIENT, client);
        model.add(ticket, CompanyXVocabulary.TICKET_PRODUCT, product);
        model.add(ticket, CompanyXVocabulary.STATUS, row.status());
        model.add(ticket, CompanyXVocabulary.PRIORITY, row.priority());
        model.add(ticket, CompanyXVocabulary.CREATED_AT, dateTime(model, row.createdAt()));
        model.add(ticket, CompanyXVocabulary.WAS_DERIVED_FROM, source);
        model.add(client, CompanyXVocabulary.REPORTED_TICKET, ticket);
        if (row.resolvedAt() != null) {
            model.add(
                    ticket,
                    CompanyXVocabulary.RESOLVED_AT,
                    dateTime(model, row.resolvedAt()));
        }
    }

    private static Resource addSourceRow(Model model, String table, int id) {
        Resource source = CompanyXVocabulary.sourceRow(table, id);
        model.add(source, RDF.type, CompanyXVocabulary.SOURCE_ROW);
        model.add(source, CompanyXVocabulary.SOURCE_TABLE, table);
        model.add(source, CompanyXVocabulary.SOURCE_PRIMARY_KEY, integer(model, id));
        model.add(source, CompanyXVocabulary.SOURCE_LOCATOR, "sql/" + table + "#id=" + id);
        return source;
    }

    private static Literal integer(Model model, int value) {
        return model.createTypedLiteral(Integer.toString(value), XSDDatatype.XSDinteger);
    }

    private static Literal date(Model model, LocalDate value) {
        return model.createTypedLiteral(value.toString(), XSDDatatype.XSDdate);
    }

    private static Literal dateTime(Model model, LocalDateTime value) {
        return model.createTypedLiteral(value.format(XSD_DATE_TIME), XSDDatatype.XSDdateTime);
    }
}

