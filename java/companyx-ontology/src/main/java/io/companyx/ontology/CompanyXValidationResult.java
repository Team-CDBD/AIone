package io.companyx.ontology;

public record CompanyXValidationResult(
        boolean conforms, int violationCount, String reportTurtle) {}

