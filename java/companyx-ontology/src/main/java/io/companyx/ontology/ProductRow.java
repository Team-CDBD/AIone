package io.companyx.ontology;

import java.time.LocalDate;

public record ProductRow(
        int id,
        String name,
        String category,
        String description,
        int priceMonthly,
        String version,
        LocalDate releaseDate,
        String status) {}

