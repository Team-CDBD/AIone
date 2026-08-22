package io.companyx.ontology;

import java.time.LocalDate;

public record CurrentProductResult(
        String contractIri,
        int contractId,
        String productIri,
        String productName,
        LocalDate startDate,
        LocalDate endDate) {}

