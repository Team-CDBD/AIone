package io.companyx.ontology;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class CompanyXSourceLoader {
    private static final Pattern INSERT_PATTERN = Pattern.compile(
            "^INSERT INTO\\s+([a-z_]+)\\s+\\(([^)]+)\\)\\s+VALUES\\s+\\((.*)\\);$");
    private static final Set<String> LEARNING_TABLES =
            Set.of("clients", "products", "contracts", "support_tickets");
    private static final DateTimeFormatter SQL_DATE_TIME =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public CompanyXSourceData load(Path datasetDirectory) throws IOException {
        Path normalizedDataset = datasetDirectory.toAbsolutePath().normalize();
        Path sqlPath = normalizedDataset.resolve("sql/02-data.sql");
        if (!Files.isRegularFile(sqlPath)) {
            throw new IOException("Company-X SQL 원본을 찾지 못했습니다: " + sqlPath);
        }

        List<ClientRow> clients = new ArrayList<>();
        List<ProductRow> products = new ArrayList<>();
        List<ContractRow> contracts = new ArrayList<>();
        List<SupportTicketRow> supportTickets = new ArrayList<>();

        List<String> lines = Files.readAllLines(sqlPath, StandardCharsets.UTF_8);
        for (int index = 0; index < lines.size(); index++) {
            ParsedInsert insert = parseInsert(lines.get(index), sqlPath, index + 1);
            if (insert == null || !LEARNING_TABLES.contains(insert.table())) {
                continue;
            }

            switch (insert.table()) {
                case "clients" -> clients.add(toClient(insert));
                case "products" -> products.add(toProduct(insert));
                case "contracts" -> contracts.add(toContract(insert));
                case "support_tickets" -> supportTickets.add(toSupportTicket(insert));
                default -> throw new IllegalStateException("지원하지 않는 학습 테이블: " + insert.table());
            }
        }

        verifyBaseline(clients, products, contracts, supportTickets);
        return new CompanyXSourceData(
                normalizedDataset, clients, products, contracts, supportTickets);
    }

    private static ParsedInsert parseInsert(String line, Path sqlPath, int lineNumber) {
        Matcher matcher = INSERT_PATTERN.matcher(line.strip());
        if (!matcher.matches()) {
            return null;
        }

        List<String> columns = List.of(matcher.group(2).split("\\s*,\\s*"));
        List<String> values = splitSqlValues(matcher.group(3), sqlPath, lineNumber);
        if (columns.size() != values.size()) {
            throw new IllegalArgumentException("%s:%d: 컬럼 %d개와 값 %d개가 다릅니다."
                    .formatted(sqlPath, lineNumber, columns.size(), values.size()));
        }

        Map<String, String> fields = new LinkedHashMap<>();
        for (int index = 0; index < columns.size(); index++) {
            fields.put(columns.get(index), values.get(index));
        }
        return new ParsedInsert(
                matcher.group(1), Collections.unmodifiableMap(fields), sqlPath, lineNumber);
    }

    private static List<String> splitSqlValues(String payload, Path sqlPath, int lineNumber) {
        List<String> values = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;

        for (int index = 0; index < payload.length(); index++) {
            char character = payload.charAt(index);
            if (character == '\'') {
                if (quoted && index + 1 < payload.length() && payload.charAt(index + 1) == '\'') {
                    current.append('\'');
                    index++;
                } else {
                    quoted = !quoted;
                }
            } else if (character == ',' && !quoted) {
                values.add(normalizeSqlValue(current.toString()));
                current.setLength(0);
            } else {
                current.append(character);
            }
        }

        if (quoted) {
            throw new IllegalArgumentException(
                    "%s:%d: 닫히지 않은 SQL 문자열입니다.".formatted(sqlPath, lineNumber));
        }
        values.add(normalizeSqlValue(current.toString()));
        return values;
    }

    private static String normalizeSqlValue(String value) {
        String normalized = value.strip();
        return normalized.equalsIgnoreCase("NULL") ? null : normalized;
    }

    private static ClientRow toClient(ParsedInsert insert) {
        return new ClientRow(
                integer(insert, "id"),
                required(insert, "name"),
                required(insert, "industry"),
                required(insert, "region"),
                required(insert, "company_size"),
                insert.fields().get("contact_name"),
                insert.fields().get("contact_email"),
                date(insert, "registered_at"));
    }

    private static ProductRow toProduct(ParsedInsert insert) {
        return new ProductRow(
                integer(insert, "id"),
                required(insert, "name"),
                required(insert, "category"),
                insert.fields().get("description"),
                integer(insert, "price_monthly"),
                insert.fields().get("version"),
                nullableDate(insert, "release_date"),
                required(insert, "status"));
    }

    private static ContractRow toContract(ParsedInsert insert) {
        return new ContractRow(
                integer(insert, "id"),
                integer(insert, "client_id"),
                integer(insert, "product_id"),
                integer(insert, "manager_id"),
                required(insert, "contract_type"),
                integer(insert, "amount"),
                date(insert, "start_date"),
                nullableDate(insert, "end_date"),
                required(insert, "status"));
    }

    private static SupportTicketRow toSupportTicket(ParsedInsert insert) {
        return new SupportTicketRow(
                integer(insert, "id"),
                integer(insert, "client_id"),
                integer(insert, "product_id"),
                nullableInteger(insert, "assignee_id"),
                required(insert, "title"),
                insert.fields().get("description"),
                required(insert, "priority"),
                required(insert, "status"),
                dateTime(insert, "created_at"),
                nullableDateTime(insert, "resolved_at"));
    }

    private static String required(ParsedInsert insert, String column) {
        String value = insert.fields().get(column);
        if (value == null) {
            throw invalidValue(insert, column, "필수 값이 NULL입니다.");
        }
        return value;
    }

    private static int integer(ParsedInsert insert, String column) {
        return Integer.parseInt(required(insert, column));
    }

    private static Integer nullableInteger(ParsedInsert insert, String column) {
        String value = insert.fields().get(column);
        return value == null ? null : Integer.valueOf(value);
    }

    private static LocalDate date(ParsedInsert insert, String column) {
        return LocalDate.parse(required(insert, column));
    }

    private static LocalDate nullableDate(ParsedInsert insert, String column) {
        String value = insert.fields().get(column);
        return value == null ? null : LocalDate.parse(value);
    }

    private static LocalDateTime dateTime(ParsedInsert insert, String column) {
        return LocalDateTime.parse(required(insert, column), SQL_DATE_TIME);
    }

    private static LocalDateTime nullableDateTime(ParsedInsert insert, String column) {
        String value = insert.fields().get(column);
        return value == null ? null : LocalDateTime.parse(value, SQL_DATE_TIME);
    }

    private static IllegalArgumentException invalidValue(
            ParsedInsert insert, String column, String message) {
        return new IllegalArgumentException("%s:%d [%s.%s] %s"
                .formatted(
                        insert.sqlPath(),
                        insert.lineNumber(),
                        insert.table(),
                        column,
                        message));
    }

    private static void verifyBaseline(
            List<ClientRow> clients,
            List<ProductRow> products,
            List<ContractRow> contracts,
            List<SupportTicketRow> supportTickets) {
        Map<String, Integer> expected = Map.of(
                "clients", 30,
                "products", 12,
                "contracts", 65,
                "support_tickets", 120);
        Map<String, Integer> actual = Map.of(
                "clients", clients.size(),
                "products", products.size(),
                "contracts", contracts.size(),
                "support_tickets", supportTickets.size());
        if (!actual.equals(expected)) {
            throw new IllegalArgumentException(
                    "학습 데이터 기준선이 달라졌습니다. expected=" + expected + ", actual=" + actual);
        }
    }

    private record ParsedInsert(
            String table, Map<String, String> fields, Path sqlPath, int lineNumber) {}
}

