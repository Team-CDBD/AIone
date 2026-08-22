package io.companyx.ontology;

import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.ResourceFactory;

public final class CompanyXVocabulary {
    public static final String CX_NS = "https://company-x.example/ontology/";
    public static final String RESOURCE_NS = "https://company-x.example/resource/";
    public static final String PROV_NS = "http://www.w3.org/ns/prov#";

    public static final Resource CLIENT = resource(CX_NS + "Client");
    public static final Resource PRODUCT = resource(CX_NS + "Product");
    public static final Resource CONTRACT = resource(CX_NS + "Contract");
    public static final Resource SUPPORT_TICKET = resource(CX_NS + "SupportTicket");
    public static final Resource SOURCE_ROW = resource(CX_NS + "SourceRow");

    public static final Property HAS_CONTRACT = property("hasContract");
    public static final Property CONTRACT_CLIENT = property("contractClient");
    public static final Property CONTRACT_PRODUCT = property("contractProduct");
    public static final Property REPORTED_TICKET = property("reportedTicket");
    public static final Property TICKET_CLIENT = property("ticketClient");
    public static final Property TICKET_PRODUCT = property("ticketProduct");
    public static final Property RECORD_ID = property("recordId");
    public static final Property STATUS = property("status");
    public static final Property START_DATE = property("startDate");
    public static final Property END_DATE = property("endDate");
    public static final Property AMOUNT = property("amount");
    public static final Property PRIORITY = property("priority");
    public static final Property CREATED_AT = property("createdAt");
    public static final Property RESOLVED_AT = property("resolvedAt");
    public static final Property SOURCE_TABLE = property("sourceTable");
    public static final Property SOURCE_PRIMARY_KEY = property("sourcePrimaryKey");
    public static final Property SOURCE_LOCATOR = property("sourceLocator");
    public static final Property WAS_DERIVED_FROM =
            ResourceFactory.createProperty(PROV_NS, "wasDerivedFrom");

    private CompanyXVocabulary() {}

    public static Resource client(int id) {
        return resource(RESOURCE_NS + "client/" + id);
    }

    public static Resource product(int id) {
        return resource(RESOURCE_NS + "product/" + id);
    }

    public static Resource contract(int id) {
        return resource(RESOURCE_NS + "contract/" + id);
    }

    public static Resource ticket(int id) {
        return resource(RESOURCE_NS + "ticket/" + id);
    }

    public static Resource sourceRow(String table, int id) {
        return resource(RESOURCE_NS + "source/" + table + "/" + id);
    }

    private static Property property(String localName) {
        return ResourceFactory.createProperty(CX_NS, localName);
    }

    private static Resource resource(String iri) {
        return ResourceFactory.createResource(iri);
    }
}

