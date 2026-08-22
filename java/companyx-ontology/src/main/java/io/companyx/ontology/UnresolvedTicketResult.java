package io.companyx.ontology;

public record UnresolvedTicketResult(
        String ticketIri,
        int ticketId,
        String title,
        String status,
        String priority,
        String productIri,
        String productName) {}

