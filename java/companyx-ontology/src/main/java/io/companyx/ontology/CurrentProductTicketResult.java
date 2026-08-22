package io.companyx.ontology;

public record CurrentProductTicketResult(
        String ticketIri,
        int ticketId,
        String title,
        String status,
        String productIri,
        String productName,
        int contractId) {}

