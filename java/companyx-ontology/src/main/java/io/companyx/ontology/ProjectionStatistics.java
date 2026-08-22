package io.companyx.ontology;

public record ProjectionStatistics(
        int contractInstances,
        int contractPairs,
        int supportTicketInstances,
        int supportTicketPairs,
        long triples) {}

