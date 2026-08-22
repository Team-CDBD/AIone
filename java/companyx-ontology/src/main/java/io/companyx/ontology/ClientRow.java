package io.companyx.ontology;

import java.time.LocalDate;

public record ClientRow(
        int id,
        String name,
        String industry,
        String region,
        String companySize,
        String contactName,
        String contactEmail,
        LocalDate registeredAt) {}

