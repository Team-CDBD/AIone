package io.companyx.ontology;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QuerySolution;
import org.apache.jena.query.QuerySolutionMap;
import org.apache.jena.query.ResultSet;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ResourceFactory;

public final class CompanyXQueries {
    private final Path queryDirectory;

    public CompanyXQueries(Path queryDirectory) {
        this.queryDirectory = queryDirectory.toAbsolutePath().normalize();
    }

    public List<CurrentProductResult> currentProducts(
            Model model, int clientId, LocalDate asOf) throws IOException {
        return select(
                model,
                "current-products.rq",
                bindings(clientId, asOf),
                row -> new CurrentProductResult(
                        row.getResource("contract").getURI(),
                        row.getLiteral("contractId").getInt(),
                        row.getResource("product").getURI(),
                        row.getLiteral("productName").getString(),
                        LocalDate.parse(row.getLiteral("start").getLexicalForm()),
                        row.contains("end")
                                ? LocalDate.parse(row.getLiteral("end").getLexicalForm())
                                : null));
    }

    public List<UnresolvedTicketResult> unresolvedTickets(Model model, int clientId)
            throws IOException {
        return select(
                model,
                "unresolved-tickets.rq",
                bindings(clientId, null),
                row -> new UnresolvedTicketResult(
                        row.getResource("ticket").getURI(),
                        row.getLiteral("ticketId").getInt(),
                        row.getLiteral("title").getString(),
                        row.getLiteral("ticketStatus").getString(),
                        row.getLiteral("priority").getString(),
                        row.getResource("product").getURI(),
                        row.getLiteral("productName").getString()));
    }

    public List<CurrentProductTicketResult> unresolvedTicketsForCurrentProducts(
            Model model, int clientId, LocalDate asOf) throws IOException {
        return select(
                model,
                "unresolved-tickets-for-current-products.rq",
                bindings(clientId, asOf),
                row -> new CurrentProductTicketResult(
                        row.getResource("ticket").getURI(),
                        row.getLiteral("ticketId").getInt(),
                        row.getLiteral("title").getString(),
                        row.getLiteral("ticketStatus").getString(),
                        row.getResource("product").getURI(),
                        row.getLiteral("productName").getString(),
                        row.getLiteral("contractId").getInt()));
    }

    private <T> List<T> select(
            Model model,
            String queryFile,
            QuerySolutionMap substitutions,
            Function<QuerySolution, T> mapper)
            throws IOException {
        String query = readQuery(queryFile);
        List<T> rows = new ArrayList<>();
        try (QueryExecution execution = QueryExecution.model(model)
                .query(query)
                .substitution(substitutions)
                .build()) {
            ResultSet resultSet = execution.execSelect();
            while (resultSet.hasNext()) {
                rows.add(mapper.apply(resultSet.nextSolution()));
            }
        }
        return List.copyOf(rows);
    }

    private QuerySolutionMap bindings(int clientId, LocalDate asOf) {
        QuerySolutionMap substitutions = new QuerySolutionMap();
        substitutions.add("client", CompanyXVocabulary.client(clientId));
        if (asOf != null) {
            substitutions.add(
                    "asOf",
                    ResourceFactory.createTypedLiteral(
                            asOf.toString(), XSDDatatype.XSDdate));
        }
        return substitutions;
    }

    private String readQuery(String queryFile) throws IOException {
        Path path = queryDirectory.resolve(queryFile).normalize();
        if (!path.startsWith(queryDirectory) || !Files.isRegularFile(path)) {
            throw new IOException("Company-X SPARQL query를 찾지 못했습니다: " + path);
        }
        return Files.readString(path, StandardCharsets.UTF_8);
    }
}

