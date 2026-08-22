package io.companyx.ontology.prototype.graphcomparison;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

final class GraphComparisonContractTest {
    private static final Path DATASET = Path.of(System.getProperty(
            "companyx.dataset", "/Users/anseonghun/Downloads/companyx-dataset-v1.0"));

    @Test
    void jenaAnswersTheOfficialClientProductsQuestionThroughTheSharedSeam() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.CLIENT_A_PRODUCTS));
        }

        assertEquals("jena", result.engine());
        assertEquals("SPARQL", result.queryLanguage());
        assertEquals(
                List.of(
                        new GraphAnswer(
                                "product_3",
                                "Product-S1",
                                Map.of("contractId", "57", "status", "active"),
                                List.of(
                                        "graph/nodes.json#product_3",
                                        "graph/edges.json#index=158")),
                        new GraphAnswer(
                                "product_7",
                                "Product-C3",
                                Map.of("contractId", "44", "status", "active"),
                                List.of(
                                        "graph/nodes.json#product_7",
                                        "graph/edges.json#index=136"))),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialReverseTraversalQuestionThroughTheSharedSeam() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.PRODUCT_C1_CLIENTS));
        }

        assertEquals(
                List.of(
                        answer("client_4", "Client-D", 59),
                        answer("client_8", "Client-H", 55),
                        answer("client_17", "Client-Q", 98),
                        answer("client_20", "Client-T", 69),
                        answer("client_22", "Client-V", 166),
                        answer("client_25", "Client-Y", 84)),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialCloudDivisionEmployeesQuestionThroughTheSharedSeam()
            throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.CLOUD_DIVISION_EMPLOYEES));
        }

        assertEquals(
                List.of(
                        employee("employee_2", "안진우", 1),
                        employee("employee_7", "강현우", 6),
                        employee("employee_8", "서재원", 7),
                        employee("employee_10", "김도윤", 9),
                        employee("employee_20", "조동현", 19),
                        employee("employee_22", "이지훈", 21),
                        employee("employee_27", "황다은", 26),
                        employee("employee_33", "한은지", 32),
                        employee("employee_39", "황재원", 38),
                        employee("employee_45", "김준혁", 44)),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialClientAccountManagersQuestionThroughTheSharedSeam()
            throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.CLIENT_B_ACCOUNT_MANAGERS));
        }

        assertEquals(
                List.of(
                        employee("employee_17", "류서연", 97),
                        employee("employee_27", "황다은", 77),
                        employee("employee_28", "강유진", 74),
                        employee("employee_34", "신동현", 62),
                        employee("employee_45", "김준혁", 169)),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialTwoHopQuestionWithBothRelationshipSources() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.PRODUCT_D1_PROJECTS));
        }

        assertEquals(
                List.of(
                        project("project_2", "Client-B CI/CD 파이프라인 구축", 96, 177),
                        project("project_3", "Client-Q AI 예측 모델 구축", 142, 179),
                        project("project_5", "Client-AB DevOps 전환", 92, 183),
                        project("project_13", "Client-B CI/CD 파이프라인 구축", 96, 199),
                        project("project_21", "Client-Y 데이터 거버넌스", 82, 215),
                        project("project_22", "Client-B 하이브리드 클라우드", 96, 217)),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialAggregateQuestionWithEveryCountedSource() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.MOST_REPORTED_PRODUCT));
        }

        assertEquals(List.of(mostReportedProduct()), result.answers());
    }

    @Test
    void jenaAnswersTheOfficialDepartmentHeadQuestionThroughTheSharedSeam() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.MANAGEMENT_SUPPORT_HEAD));
        }

        assertEquals(List.of(employee("employee_1", "윤소연", 45)), result.answers());
    }

    @Test
    void jenaAnswersTheOfficialInProgressProjectLeadersQuestionWithoutDuplicateEmployees()
            throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.IN_PROGRESS_PROJECT_LEADERS));
        }

        assertEquals(
                List.of(
                        projectLeader("employee_2", "안진우", new int[] {20}, new int[] {214}),
                        projectLeader("employee_3", "조재원", new int[] {39}, new int[] {252}),
                        projectLeader("employee_7", "강현우", new int[] {1, 29}, new int[] {176, 232}),
                        projectLeader("employee_8", "서재원", new int[] {19, 31, 38}, new int[] {212, 236, 250}),
                        projectLeader("employee_13", "권소연", new int[] {28}, new int[] {230}),
                        projectLeader("employee_15", "한태호", new int[] {6, 17}, new int[] {186, 208}),
                        projectLeader("employee_17", "류서연", new int[] {24}, new int[] {222}),
                        projectLeader("employee_20", "조동현", new int[] {4}, new int[] {182}),
                        projectLeader("employee_31", "박성민", new int[] {36}, new int[] {246}),
                        projectLeader("employee_44", "장미라", new int[] {11, 16}, new int[] {196, 206}),
                        projectLeader("employee_45", "김준혁", new int[] {14, 15, 37}, new int[] {202, 204, 248})),
                result.answers());
    }

    @Test
    void jenaAnswersTheOfficialProductIssuesQuestionWithRelationIdentityAndProperties()
            throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.PRODUCT_S1_ISSUES));
        }

        assertEquals(
                List.of(
                        issue(2, "client_4", "Client-D", "low", 256),
                        issue(12, "client_10", "Client-J", "high", 266),
                        issue(14, "client_24", "Client-X", "high", 268),
                        issue(19, "client_22", "Client-V", "low", 273),
                        issue(51, "client_15", "Client-O", "critical", 303),
                        issue(79, "client_19", "Client-S", "high", 323),
                        issue(103, "client_27", "Client-AA", "medium", 338),
                        issue(114, "client_5", "Client-E", "high", 348)),
                result.answers());
    }

    @Test
    void jenaPreservesEveryJointWinnerForTheOfficialMostAccountsQuestion() throws Exception {
        GraphOperationResult result;
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            result = tool.query(new GraphQuery(GraphQuestion.MOST_ACCOUNTS_MANAGERS));
        }

        assertEquals(
                List.of(
                        accountLeader("employee_18", "안소연", 60, 81, 85, 135),
                        accountLeader("employee_43", "조현우", 52, 133, 150, 172),
                        accountLeader("employee_45", "김준혁", 66, 154, 161, 169)),
                result.answers());
    }

    @Test
    void jenaLabelsEveryOfficialGraphAnswerAsProjectionAndItsEvidenceAsJsonView()
            throws Exception {
        try (GraphTool tool = JenaGraphTool.load(DATASET.resolve("graph"))) {
            for (GraphQuestion question : GraphQuestion.values()) {
                GraphOperationResult result = tool.query(new GraphQuery(question));

                assertEquals(GraphEvidenceContext.OFFICIAL_JSON_RDF_PROJECTION, result.evidenceContext());
                assertEquals("rdf_projection", result.evidenceContext().answerDataRole());
                assertEquals("official_json_graph_view", result.evidenceContext().evidenceRole());
            }
        }
    }

    private static GraphAnswer answer(String id, String name, int edgeIndex) {
        return new GraphAnswer(
                id,
                name,
                Map.of(),
                List.of("graph/nodes.json#" + id, "graph/edges.json#index=" + edgeIndex));
    }

    private static GraphAnswer employee(String id, String name, int edgeIndex) {
        return answer(id, name, edgeIndex);
    }

    private static GraphAnswer project(String id, String name, int usesEdge, int projectEdge) {
        return new GraphAnswer(
                id,
                name,
                Map.of(),
                List.of(
                        "graph/nodes.json#" + id,
                        "graph/edges.json#index=" + usesEdge,
                        "graph/edges.json#index=" + projectEdge));
    }

    private static GraphAnswer mostReportedProduct() {
        return new GraphAnswer(
                "product_12",
                "Product-T2",
                Map.of("issueCount", "13"),
                List.of(
                        "graph/nodes.json#product_12",
                        "graph/edges.json#index=269",
                        "graph/edges.json#index=274",
                        "graph/edges.json#index=278",
                        "graph/edges.json#index=286",
                        "graph/edges.json#index=288",
                        "graph/edges.json#index=294",
                        "graph/edges.json#index=299",
                        "graph/edges.json#index=307",
                        "graph/edges.json#index=315",
                        "graph/edges.json#index=321",
                        "graph/edges.json#index=322",
                        "graph/edges.json#index=346",
                        "graph/edges.json#index=351"));
    }

    private static GraphAnswer projectLeader(
            String id, String name, int[] projectIds, int[] edgeIndexes) {
        java.util.ArrayList<String> sourceIds = new java.util.ArrayList<>();
        java.util.ArrayList<String> projects = new java.util.ArrayList<>();
        sourceIds.add("graph/nodes.json#" + id);
        for (int index = 0; index < projectIds.length; index++) {
            String projectId = "project_" + projectIds[index];
            projects.add(projectId);
            sourceIds.add("graph/nodes.json#" + projectId);
            sourceIds.add("graph/edges.json#index=" + edgeIndexes[index]);
        }
        return new GraphAnswer(
                id,
                name,
                Map.of(
                        "projectCount", Integer.toString(projectIds.length),
                        "projectIds", String.join(",", projects)),
                sourceIds);
    }

    private static GraphAnswer issue(
            int ticketId, String clientId, String clientName, String priority, int edgeIndex) {
        return new GraphAnswer(
                "ticket_" + ticketId,
                clientName,
                Map.of("clientId", clientId, "priority", priority),
                List.of(
                        "graph/nodes.json#" + clientId,
                        "graph/nodes.json#product_3",
                        "graph/edges.json#index=" + edgeIndex));
    }

    private static GraphAnswer accountLeader(
            String id, String name, int first, int second, int third, int fourth) {
        return new GraphAnswer(
                id,
                name,
                Map.of("accountCount", "4"),
                List.of(
                        "graph/nodes.json#" + id,
                        "graph/edges.json#index=" + first,
                        "graph/edges.json#index=" + second,
                        "graph/edges.json#index=" + third,
                        "graph/edges.json#index=" + fourth));
    }
}
