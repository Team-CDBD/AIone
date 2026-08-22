package io.companyx.ontology;

import java.time.LocalDateTime;

public record SupportTicketRow(
        int id,
        int clientId,
        int productId,
        Integer assigneeId,
        String title,
        String description,
        String priority,
        String status,
        LocalDateTime createdAt,
        LocalDateTime resolvedAt) {}

