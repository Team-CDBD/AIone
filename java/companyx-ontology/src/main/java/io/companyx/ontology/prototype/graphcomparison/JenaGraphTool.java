package io.companyx.ontology.prototype.graphcomparison;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.apache.jena.query.Query;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.ResultSet;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/** Projects the supplied official JSON graph into an in-memory Jena model. */
public final class JenaGraphTool implements GraphTool {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String CLIENT_A_PRODUCTS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource ?contractId ?status
            WHERE {
              ?client cx:sourceId "client_1" .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?client ;
                    cx:edgeTarget ?product ;
                    cx:edgeRelation "USES" ;
                    cx:sourceLocator ?edgeSource ;
                    cx:contract_id ?contractId ;
                    cx:status ?status .
              ?product cx:sourceId ?id ;
                       cx:sourceLocator ?nodeSource ;
                       rdfs:label ?name .
            }
            ORDER BY ?id
            """;
    private static final String PRODUCT_C1_CLIENTS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource
            WHERE {
              ?product cx:sourceId "product_1" .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?client ;
                    cx:edgeTarget ?product ;
                    cx:edgeRelation "USES" ;
                    cx:sourceLocator ?edgeSource .
              ?client cx:sourceId ?id ;
                      cx:sourceLocator ?nodeSource ;
                      rdfs:label ?name .
            }
            """;
    private static final String CLOUD_DIVISION_EMPLOYEES = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource
            WHERE {
              ?department cx:sourceId "dept_2" .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?employee ;
                    cx:edgeTarget ?department ;
                    cx:edgeRelation "BELONGS_TO" ;
                    cx:sourceLocator ?edgeSource .
              ?employee cx:sourceId ?id ;
                        cx:sourceLocator ?nodeSource ;
                        rdfs:label ?name .
            }
            """;
    private static final String CLIENT_B_ACCOUNT_MANAGERS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource
            WHERE {
              ?client cx:sourceId "client_2" .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?employee ;
                    cx:edgeTarget ?client ;
                    cx:edgeRelation "MANAGES_ACCOUNT" ;
                    cx:sourceLocator ?edgeSource .
              ?employee cx:sourceId ?id ;
                        cx:sourceLocator ?nodeSource ;
                        rdfs:label ?name .
            }
            """;
    private static final String PRODUCT_D1_PROJECTS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource
            WHERE {
              ?product cx:sourceId "product_5" .
              ?uses a cx:GraphEdge ;
                    cx:edgeSource ?client ;
                    cx:edgeTarget ?product ;
                    cx:edgeRelation "USES" ;
                    cx:sourceLocator ?usesSource .
              ?hasProject a cx:GraphEdge ;
                          cx:edgeSource ?client ;
                          cx:edgeTarget ?project ;
                          cx:edgeRelation "HAS_PROJECT" ;
                          cx:sourceLocator ?projectSource .
              ?project cx:sourceId ?id ;
                       cx:sourceLocator ?nodeSource ;
                       rdfs:label ?name .
              BIND(CONCAT(?usesSource, "|", ?projectSource) AS ?edgeSource)
            }
            """;
    private static final String MOST_REPORTED_PRODUCT = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource ?issueCount
            WHERE {
              {
                SELECT ?product (COUNT(?countEdge) AS ?issueCount)
                WHERE {
                  ?countEdge a cx:GraphEdge ;
                             cx:edgeTarget ?product ;
                             cx:edgeRelation "REPORTED_ISSUE" .
                }
                GROUP BY ?product
                ORDER BY DESC(?issueCount) ?product
                LIMIT 1
              }
              ?product cx:sourceId ?id ;
                       cx:sourceLocator ?nodeSource ;
                       rdfs:label ?name .
              ?evidenceEdge a cx:GraphEdge ;
                            cx:edgeTarget ?product ;
                            cx:edgeRelation "REPORTED_ISSUE" ;
                            cx:sourceLocator ?edgeSource .
            }
            """;
    private static final String MANAGEMENT_SUPPORT_HEAD = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource
            WHERE {
              ?department cx:sourceId "dept_1" .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?department ;
                    cx:edgeTarget ?employee ;
                    cx:edgeRelation "HEAD_IS" ;
                    cx:sourceLocator ?edgeSource .
              ?employee cx:sourceId ?id ;
                        cx:sourceLocator ?nodeSource ;
                        rdfs:label ?name .
            }
            """;
    private static final String IN_PROGRESS_PROJECT_LEADERS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?projectId ?projectSource ?edgeSource
            WHERE {
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?employee ;
                    cx:edgeTarget ?project ;
                    cx:edgeRelation "LEADS" ;
                    cx:sourceLocator ?edgeSource .
              ?employee cx:sourceId ?id ;
                        cx:sourceLocator ?nodeSource ;
                        rdfs:label ?name .
              ?project cx:sourceId ?projectId ;
                       cx:sourceLocator ?projectSource ;
                       cx:status "in_progress" .
            }
            """;
    private static final String PRODUCT_S1_ISSUES = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource ?clientId ?priority
            WHERE {
              ?product cx:sourceId "product_3" ;
                       cx:sourceLocator ?productSource .
              ?edge a cx:GraphEdge ;
                    cx:edgeSource ?client ;
                    cx:edgeTarget ?product ;
                    cx:edgeRelation "REPORTED_ISSUE" ;
                    cx:sourceLocator ?issueSource ;
                    cx:ticket_id ?ticketId ;
                    cx:priority ?priority .
              ?client cx:sourceId ?clientId ;
                      cx:sourceLocator ?nodeSource ;
                      rdfs:label ?name .
              BIND(CONCAT("ticket_", STR(?ticketId)) AS ?id)
              BIND(CONCAT(?productSource, "|", ?issueSource) AS ?edgeSource)
            }
            """;
    private static final String MOST_ACCOUNTS_MANAGERS = """
            PREFIX cx: <https://company-x.example/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?id ?name ?nodeSource ?edgeSource ?accountCount
            WHERE {
              {
                SELECT (MAX(?candidateCount) AS ?maxCount)
                WHERE {
                  {
                    SELECT ?candidate (COUNT(?candidateEdge) AS ?candidateCount)
                    WHERE {
                      ?candidateEdge a cx:GraphEdge ;
                                     cx:edgeSource ?candidate ;
                                     cx:edgeRelation "MANAGES_ACCOUNT" .
                    }
                    GROUP BY ?candidate
                  }
                }
              }
              {
                SELECT ?employee (COUNT(?countEdge) AS ?accountCount)
                WHERE {
                  ?countEdge a cx:GraphEdge ;
                             cx:edgeSource ?employee ;
                             cx:edgeRelation "MANAGES_ACCOUNT" .
                }
                GROUP BY ?employee
              }
              FILTER (?accountCount = ?maxCount)
              ?employee cx:sourceId ?id ;
                        cx:sourceLocator ?nodeSource ;
                        rdfs:label ?name .
              ?evidenceEdge a cx:GraphEdge ;
                            cx:edgeSource ?employee ;
                            cx:edgeRelation "MANAGES_ACCOUNT" ;
                            cx:sourceLocator ?edgeSource .
            }
            """;
    private static final QueryTemplate CLIENT_A_PRODUCTS_TEMPLATE =
            prepared(CLIENT_A_PRODUCTS);
    private static final QueryTemplate PRODUCT_C1_CLIENTS_TEMPLATE =
            prepared(PRODUCT_C1_CLIENTS);
    private static final QueryTemplate CLOUD_DIVISION_EMPLOYEES_TEMPLATE =
            prepared(CLOUD_DIVISION_EMPLOYEES);
    private static final QueryTemplate CLIENT_B_ACCOUNT_MANAGERS_TEMPLATE =
            prepared(CLIENT_B_ACCOUNT_MANAGERS);
    private static final QueryTemplate PRODUCT_D1_PROJECTS_TEMPLATE =
            prepared(PRODUCT_D1_PROJECTS);
    private static final QueryTemplate MOST_REPORTED_PRODUCT_TEMPLATE =
            prepared(MOST_REPORTED_PRODUCT);
    private static final QueryTemplate MANAGEMENT_SUPPORT_HEAD_TEMPLATE =
            prepared(MANAGEMENT_SUPPORT_HEAD);
    private static final QueryTemplate IN_PROGRESS_PROJECT_LEADERS_TEMPLATE =
            prepared(IN_PROGRESS_PROJECT_LEADERS);
    private static final QueryTemplate PRODUCT_S1_ISSUES_TEMPLATE =
            prepared(PRODUCT_S1_ISSUES);
    private static final QueryTemplate MOST_ACCOUNTS_MANAGERS_TEMPLATE =
            prepared(MOST_ACCOUNTS_MANAGERS);

    private final Model model;

    private JenaGraphTool(Model model) {
        this.model = model;
    }

    public static JenaGraphTool load(Path graphDirectory) throws IOException {
        return new JenaGraphTool(loadModel(graphDirectory));
    }

    static Model loadModel(Path graphDirectory) throws IOException {
        Path normalized = graphDirectory.toAbsolutePath().normalize();
        Path nodesPath = normalized.resolve("nodes.json");
        Path edgesPath = normalized.resolve("edges.json");
        if (!Files.isRegularFile(nodesPath) || !Files.isRegularFile(edgesPath)) {
            throw new IOException("Company-X graph JSON을 찾지 못했습니다: " + normalized);
        }

        JsonNode nodes = JSON.readTree(nodesPath.toFile());
        JsonNode edges = JSON.readTree(edgesPath.toFile());
        OfficialGraphSourceValidator.requireValid(nodes, edges);
        Model model = ModelFactory.createDefaultModel();
        model.setNsPrefix("cx", OfficialGraphVocabulary.CX);
        try {
            model.read(ontologyPath().toUri().toString());
            addNodes(model, nodes);
            addEdges(model, edges);
            JenaOfficialGraphSemanticValidator.requireValid(model);
            return model;
        } catch (RuntimeException error) {
            model.close();
            throw error;
        }
    }

    @Override
    public GraphOperationResult query(GraphQuery query) {
        if (query.question() == GraphQuestion.MOST_REPORTED_PRODUCT) {
            return mostReportedProduct();
        }
        if (query.question() == GraphQuestion.IN_PROGRESS_PROJECT_LEADERS) {
            return inProgressProjectLeaders();
        }
        if (query.question() == GraphQuestion.MOST_ACCOUNTS_MANAGERS) {
            return mostAccountsManagers();
        }
        QueryTemplate template = switch (query.question()) {
            case CLIENT_A_PRODUCTS -> CLIENT_A_PRODUCTS_TEMPLATE;
            case PRODUCT_C1_CLIENTS -> PRODUCT_C1_CLIENTS_TEMPLATE;
            case CLOUD_DIVISION_EMPLOYEES -> CLOUD_DIVISION_EMPLOYEES_TEMPLATE;
            case CLIENT_B_ACCOUNT_MANAGERS -> CLIENT_B_ACCOUNT_MANAGERS_TEMPLATE;
            case PRODUCT_D1_PROJECTS -> PRODUCT_D1_PROJECTS_TEMPLATE;
            case MOST_REPORTED_PRODUCT -> throw new IllegalStateException("집계 분기 누락");
            case MANAGEMENT_SUPPORT_HEAD -> MANAGEMENT_SUPPORT_HEAD_TEMPLATE;
            case IN_PROGRESS_PROJECT_LEADERS -> throw new IllegalStateException("그룹 분기 누락");
            case PRODUCT_S1_ISSUES -> PRODUCT_S1_ISSUES_TEMPLATE;
            case MOST_ACCOUNTS_MANAGERS -> throw new IllegalStateException("집계 분기 누락");
        };

        List<GraphAnswer> answers = new ArrayList<>();
        try (QueryExecution execution = QueryExecution.model(model)
                .query(template.query())
                .build()) {
            ResultSet rows = execution.execSelect();
            while (rows.hasNext()) {
                var row = rows.nextSolution();
                List<String> sourceIds = new ArrayList<>();
                sourceIds.add(row.getLiteral("nodeSource").getString());
                sourceIds.addAll(List.of(row.getLiteral("edgeSource").getString().split("\\|")));
                Map<String, String> details = switch (query.question()) {
                    case CLIENT_A_PRODUCTS -> Map.of(
                            "contractId",
                            row.getLiteral("contractId").getLexicalForm(),
                            "status",
                            row.getLiteral("status").getString());
                    case PRODUCT_S1_ISSUES -> Map.of(
                            "clientId",
                            row.getLiteral("clientId").getString(),
                            "priority",
                            row.getLiteral("priority").getString());
                    default -> Map.of();
                };
                answers.add(new GraphAnswer(
                        row.getLiteral("id").getString(),
                        row.getLiteral("name").getString(),
                        details,
                        sourceIds));
            }
        }
        answers.sort(Comparator.comparingInt(answer -> sourceNumber(answer.id())));
        return new GraphOperationResult("jena", "SPARQL", template.text(), answers, List.of());
    }

    private GraphOperationResult mostReportedProduct() {
        String id = null;
        String name = null;
        String nodeSource = null;
        String issueCount = null;
        List<String> edgeSources = new ArrayList<>();
        try (QueryExecution execution = QueryExecution.model(model)
                .query(MOST_REPORTED_PRODUCT_TEMPLATE.query())
                .build()) {
            ResultSet rows = execution.execSelect();
            while (rows.hasNext()) {
                var row = rows.nextSolution();
                id = row.getLiteral("id").getString();
                name = row.getLiteral("name").getString();
                nodeSource = row.getLiteral("nodeSource").getString();
                issueCount = Integer.toString(row.getLiteral("issueCount").getInt());
                edgeSources.add(row.getLiteral("edgeSource").getString());
            }
        }
        edgeSources.sort(Comparator.comparingInt(JenaGraphTool::locatorIndex));
        List<String> sourceIds = new ArrayList<>();
        sourceIds.add(nodeSource);
        sourceIds.addAll(edgeSources);
        GraphAnswer answer = new GraphAnswer(
                id, name, Map.of("issueCount", issueCount), sourceIds);
        return new GraphOperationResult(
                "jena", "SPARQL", MOST_REPORTED_PRODUCT, List.of(answer), List.of());
    }

    private GraphOperationResult inProgressProjectLeaders() {
        Map<String, String> names = new HashMap<>();
        Map<String, String> nodeSources = new HashMap<>();
        Map<String, List<ProjectEvidence>> projectsByLeader = new HashMap<>();
        try (QueryExecution execution = QueryExecution.model(model)
                .query(IN_PROGRESS_PROJECT_LEADERS_TEMPLATE.query())
                .build()) {
            ResultSet rows = execution.execSelect();
            while (rows.hasNext()) {
                var row = rows.nextSolution();
                String id = row.getLiteral("id").getString();
                names.put(id, row.getLiteral("name").getString());
                nodeSources.put(id, row.getLiteral("nodeSource").getString());
                projectsByLeader
                        .computeIfAbsent(id, ignored -> new ArrayList<>())
                        .add(new ProjectEvidence(
                                row.getLiteral("projectId").getString(),
                                row.getLiteral("projectSource").getString(),
                                row.getLiteral("edgeSource").getString()));
            }
        }

        List<GraphAnswer> answers = new ArrayList<>();
        projectsByLeader.forEach((id, projects) -> {
            projects.sort(Comparator.comparingInt(project -> sourceNumber(project.projectId())));
            List<String> sourceIds = new ArrayList<>();
            sourceIds.add(nodeSources.get(id));
            List<String> projectIds = new ArrayList<>();
            for (ProjectEvidence project : projects) {
                projectIds.add(project.projectId());
                sourceIds.add(project.projectSource());
                sourceIds.add(project.edgeSource());
            }
            answers.add(new GraphAnswer(
                    id,
                    names.get(id),
                    Map.of(
                            "projectCount", Integer.toString(projects.size()),
                            "projectIds", String.join(",", projectIds)),
                    sourceIds));
        });
        answers.sort(Comparator.comparingInt(answer -> sourceNumber(answer.id())));
        return new GraphOperationResult(
                "jena", "SPARQL", IN_PROGRESS_PROJECT_LEADERS, answers, List.of());
    }

    private GraphOperationResult mostAccountsManagers() {
        Map<String, String> names = new HashMap<>();
        Map<String, String> nodeSources = new HashMap<>();
        Map<String, String> counts = new HashMap<>();
        Map<String, List<String>> edgesByManager = new HashMap<>();
        try (QueryExecution execution = QueryExecution.model(model)
                .query(MOST_ACCOUNTS_MANAGERS_TEMPLATE.query())
                .build()) {
            ResultSet rows = execution.execSelect();
            while (rows.hasNext()) {
                var row = rows.nextSolution();
                String id = row.getLiteral("id").getString();
                names.put(id, row.getLiteral("name").getString());
                nodeSources.put(id, row.getLiteral("nodeSource").getString());
                counts.put(id, Integer.toString(row.getLiteral("accountCount").getInt()));
                edgesByManager
                        .computeIfAbsent(id, ignored -> new ArrayList<>())
                        .add(row.getLiteral("edgeSource").getString());
            }
        }

        List<GraphAnswer> answers = new ArrayList<>();
        edgesByManager.forEach((id, edges) -> {
            edges.sort(Comparator.comparingInt(JenaGraphTool::locatorIndex));
            List<String> sourceIds = new ArrayList<>();
            sourceIds.add(nodeSources.get(id));
            sourceIds.addAll(edges);
            answers.add(new GraphAnswer(
                    id, names.get(id), Map.of("accountCount", counts.get(id)), sourceIds));
        });
        answers.sort(Comparator.comparingInt(answer -> sourceNumber(answer.id())));
        return new GraphOperationResult(
                "jena", "SPARQL", MOST_ACCOUNTS_MANAGERS, answers, List.of());
    }

    @Override
    public void close() {
        model.close();
    }

    private static void addNodes(Model model, JsonNode nodes) {
        for (JsonNode node : nodes) {
            String id = node.required("id").textValue();
            Resource resource = OfficialGraphVocabulary.node(id);
            model.add(resource, RDF.type, OfficialGraphVocabulary.type(node.required("type").textValue()));
            model.add(resource, OfficialGraphVocabulary.SOURCE_ID, id);
            model.add(resource, OfficialGraphVocabulary.SOURCE_LOCATOR, "graph/nodes.json#" + id);
            model.add(resource, RDFS.label, node.required("name").textValue());
            addProperties(model, resource, node.path("properties"));
        }
    }

    private static void addEdges(Model model, JsonNode edges) {
        int index = 0;
        for (JsonNode edgeNode : edges) {
            Resource edge = OfficialGraphVocabulary.edge(index);
            model.add(edge, RDF.type, OfficialGraphVocabulary.GRAPH_EDGE);
            model.add(
                    edge,
                    OfficialGraphVocabulary.EDGE_SOURCE,
                    OfficialGraphVocabulary.node(edgeNode.required("source").textValue()));
            model.add(
                    edge,
                    OfficialGraphVocabulary.EDGE_TARGET,
                    OfficialGraphVocabulary.node(edgeNode.required("target").textValue()));
            model.add(
                    edge,
                    OfficialGraphVocabulary.EDGE_RELATION,
                    edgeNode.required("relation").textValue());
            model.add(
                    edge,
                    OfficialGraphVocabulary.SOURCE_LOCATOR,
                    "graph/edges.json#index=" + index);
            addProperties(model, edge, edgeNode.path("properties"));
            index++;
        }
    }

    private static void addProperties(Model model, Resource resource, JsonNode properties) {
        properties.properties().forEach(field -> {
            var property = OfficialGraphVocabulary.property(field.getKey());
            JsonNode value = field.getValue();
            if (value.isTextual()) {
                model.add(resource, property, value.textValue());
            } else if (value.isIntegralNumber()) {
                XSDDatatype datatype = field.getKey().equals("amount")
                        ? XSDDatatype.XSDinteger
                        : XSDDatatype.XSDlong;
                model.add(
                        resource,
                        property,
                        model.createTypedLiteral(value.bigIntegerValue().toString(), datatype));
            } else if (value.isFloatingPointNumber()) {
                model.addLiteral(resource, property, value.doubleValue());
            } else if (value.isBoolean()) {
                model.addLiteral(resource, property, value.booleanValue());
            }
        });
    }

    private static int sourceNumber(String sourceId) {
        return Integer.parseInt(sourceId.substring(sourceId.lastIndexOf('_') + 1));
    }

    private static int locatorIndex(String locator) {
        return Integer.parseInt(locator.substring(locator.lastIndexOf('=') + 1));
    }

    private static QueryTemplate prepared(String text) {
        return new QueryTemplate(text, QueryFactory.create(text));
    }

    private static Path ontologyPath() {
        Path projectDirectory = Path.of(System.getProperty("companyx.project", "."))
                .toAbsolutePath()
                .normalize();
        return projectDirectory.resolve("ontology/companyx.ttl");
    }

    private record ProjectEvidence(String projectId, String projectSource, String edgeSource) {}

    private record QueryTemplate(String text, Query query) {}
}
