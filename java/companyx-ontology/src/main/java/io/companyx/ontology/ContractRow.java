package io.companyx.ontology;

import java.time.LocalDate;

public record ContractRow(
        int id,
        int clientId,
        int productId,
        int managerId,
        String contractType,
        int amount,
        LocalDate startDate,
        LocalDate endDate,
        String status) {}

