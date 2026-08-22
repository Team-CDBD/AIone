package io.companyx.ontology;

import java.io.IOException;
import java.io.PrintStream;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.RDFNode;
import org.apache.jena.rdf.model.Statement;

public final class OntologyLabCli {
    private static final Path DEFAULT_DATASET =
            Path.of("/Users/anseonghun/Downloads/companyx-dataset-v1.0");
    private static final Set<String> COMMANDS =
            Set.of("inspect", "stats", "query", "validate", "break-it", "all");

    public static void main(String[] args) throws Exception {
        Path dataset = Path.of(System.getProperty("companyx.dataset", DEFAULT_DATASET.toString()));
        Path project = Path.of(
                System.getProperty("companyx.project", System.getProperty("user.dir")));
        new OntologyLabCli().run(args, System.out, dataset, project);
    }

    public void run(String[] args, PrintStream output, Path dataset, Path project)
            throws IOException {
        Options options = Options.parse(args);
        CompanyXSourceData sourceData = new CompanyXSourceLoader().load(dataset);
        Model model = new CompanyXGraphBuilder()
                .build(sourceData, project.resolve("ontology/companyx.ttl"));
        try {
            CompanyXQueries queries = new CompanyXQueries(project.resolve("ontology/queries"));
            CompanyXValidator validator =
                    new CompanyXValidator(project.resolve("ontology/shapes/companyx-shapes.ttl"));

            switch (options.command()) {
                case "inspect" -> inspect(output, model);
                case "stats" -> stats(output, model);
                case "query" -> query(
                        output, model, queries, options.clientId(), options.asOf());
                case "validate" -> validate(output, model, validator);
                case "break-it" -> breakIt(output, model, validator);
                case "all" -> {
                    inspect(output, model);
                    stats(output, model);
                    query(output, model, queries, options.clientId(), options.asOf());
                    validate(output, model, validator);
                    breakIt(output, model, validator);
                }
                default -> throw new IllegalStateException("지원하지 않는 명령: " + options.command());
            }
        } finally {
            model.close();
        }
    }

    private static void inspect(PrintStream output, Model model) {
        output.println("\n[1] TBox — 이 세계에 어떤 종류가 있는가");
        List.of(
                        CompanyXVocabulary.CLIENT,
                        CompanyXVocabulary.PRODUCT,
                        CompanyXVocabulary.CONTRACT,
                        CompanyXVocabulary.SUPPORT_TICKET)
                .forEach(type -> output.println("- " + model.shortForm(type.getURI())));

        output.println("\n[2] RBox — Contract가 어떤 관계를 가져야 하는가");
        output.println("- cx:contractClient : Contract -> Client");
        output.println("- cx:contractProduct: Contract -> Product");
        output.println("- cx:startDate / cx:endDate / cx:status");

        output.println("\n[3] ABox — 실제 한 계약 instance, contract/44");
        CompanyXVocabulary.contract(44).inModel(model).listProperties().toList().stream()
                .sorted(Comparator.comparing(statement -> statement.getPredicate().getURI()))
                .forEach(statement -> output.printf(
                        "- %s %s%n",
                        model.shortForm(statement.getPredicate().getURI()),
                        display(model, statement)));
    }

    private static String display(Model model, Statement statement) {
        RDFNode value = statement.getObject();
        if (value.isURIResource()) {
            return model.shortForm(value.asResource().getURI());
        }
        if (value.isLiteral()) {
            return value.asLiteral().getLexicalForm();
        }
        return value.toString();
    }

    private static void stats(PrintStream output, Model model) {
        ProjectionStatistics statistics = new CompanyXStatistics().summarize(model);
        output.println("\n[실데이터 multiplicity 확인]");
        output.printf("- Contract instance : %d건%n", statistics.contractInstances());
        output.printf("- (Client, Product) : %d쌍%n", statistics.contractPairs());
        output.printf("- SupportTicket     : %d건%n", statistics.supportTicketInstances());
        output.printf("- (Client, Product) : %d쌍%n", statistics.supportTicketPairs());
        output.printf("- 전체 RDF triple   : %d개%n", statistics.triples());
        output.printf(
                "- 계약을 요약 선으로 접으면 %d건의 관계 instance가 구분되지 않습니다.%n",
                statistics.contractInstances() - statistics.contractPairs());
        output.printf(
                "- 티켓을 요약 선으로 접으면 %d건의 관계 instance가 구분되지 않습니다.%n",
                statistics.supportTicketInstances() - statistics.supportTicketPairs());
    }

    private static void query(
            PrintStream output,
            Model model,
            CompanyXQueries queries,
            int clientId,
            LocalDate asOf)
            throws IOException {
        List<CurrentProductResult> products = queries.currentProducts(model, clientId, asOf);
        List<UnresolvedTicketResult> tickets = queries.unresolvedTickets(model, clientId);
        List<CurrentProductTicketResult> related =
                queries.unresolvedTicketsForCurrentProducts(model, clientId, asOf);

        output.printf("%n[Client-%d / as-of %s]%n", clientId, asOf);
        output.println("\n현재 유효한 계약 제품");
        if (products.isEmpty()) {
            output.println("- 없음");
        }
        products.forEach(row -> output.printf(
                "- Contract %d: %s (%s ~ %s)%n",
                row.contractId(),
                row.productName(),
                row.startDate(),
                row.endDate() == null ? "종료일 없음" : row.endDate()));

        output.println("\n해결되지 않은 전체 티켓");
        if (tickets.isEmpty()) {
            output.println("- 없음");
        }
        tickets.forEach(row -> output.printf(
                "- Ticket %d: %s / %s / %s / %s%n",
                row.ticketId(), row.title(), row.productName(), row.status(), row.priority()));

        output.println("\n현재 유효한 계약 제품과 같은 제품의 미해결 티켓");
        if (related.isEmpty()) {
            output.println("- 없음");
        }
        related.forEach(row -> output.printf(
                "- Ticket %d: %s / Contract %d%n",
                row.ticketId(), row.title(), row.contractId()));
        output.println("\n주의: 이 랩은 end_date 당일을 포함하는 규칙으로 조회합니다.");
    }

    private static void validate(
            PrintStream output, Model model, CompanyXValidator validator) {
        CompanyXValidationResult result = validator.validate(model);
        output.println("\n[SHACL 정상 그래프]");
        output.println("- conforms: " + result.conforms());
        output.println("- violations: " + result.violationCount());
        if (!result.conforms()) {
            throw new IllegalStateException(result.reportTurtle());
        }
    }

    private static void breakIt(
            PrintStream output, Model model, CompanyXValidator validator) {
        Model broken = ModelFactory.createDefaultModel().add(model);
        try {
            broken.removeAll(
                    CompanyXVocabulary.contract(44),
                    CompanyXVocabulary.CONTRACT_PRODUCT,
                    null);
            CompanyXValidationResult result = validator.validate(broken);

            output.println("\n[의도적으로 망가뜨린 그래프]");
            output.println("- 제거: contract/44 -- cx:contractProduct --> product/7");
            output.println("- conforms: " + result.conforms());
            if (result.conforms()) {
                throw new IllegalStateException("필수 Product 관계 누락을 검출하지 못했습니다.");
            }
            output.println("- Message: Contract는 Product를 정확히 하나 가리켜야 한다.");
            output.println("- 예상대로 필수 Product 관계 누락을 검출했습니다.");
        } finally {
            broken.close();
        }
    }

    private record Options(String command, int clientId, LocalDate asOf) {
        private static Options parse(String[] args) {
            if (args.length == 0 || !COMMANDS.contains(args[0])) {
                throw new IllegalArgumentException(
                        "명령이 필요합니다: inspect|stats|query|validate|break-it|all");
            }

            int clientId = 1;
            LocalDate asOf = LocalDate.of(2026, 8, 3);
            for (int index = 1; index < args.length; index++) {
                String option = args[index];
                if ("--client-id".equals(option) && index + 1 < args.length) {
                    clientId = Integer.parseInt(args[++index]);
                } else if ("--as-of".equals(option) && index + 1 < args.length) {
                    asOf = LocalDate.parse(args[++index]);
                } else {
                    throw new IllegalArgumentException(
                            "알 수 없거나 값이 없는 옵션: "
                                    + option
                                    + " (args="
                                    + Arrays.toString(args)
                                    + ")");
                }
            }
            if (clientId < 1) {
                throw new IllegalArgumentException("client-id는 1 이상이어야 합니다.");
            }
            return new Options(args[0], clientId, asOf);
        }
    }
}
