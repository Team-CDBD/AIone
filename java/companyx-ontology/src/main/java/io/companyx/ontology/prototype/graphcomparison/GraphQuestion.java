package io.companyx.ontology.prototype.graphcomparison;

/** Official Company-X knowledge-graph questions exposed through the bounded MCP surface. */
public enum GraphQuestion {
    CLIENT_A_PRODUCTS("Client-A가 사용 중인 제품 목록은?"),
    PRODUCT_C1_CLIENTS("Product-C1을 사용하는 고객사는 어디야?"),
    CLOUD_DIVISION_EMPLOYEES("클라우드사업부 소속 직원들은 누구야?"),
    CLIENT_B_ACCOUNT_MANAGERS("서울물산 담당 엔지니어는 누구야?"),
    PRODUCT_D1_PROJECTS("Product-D1 제품과 관련된 프로젝트는?"),
    MOST_REPORTED_PRODUCT("기술 지원 이슈가 가장 많은 제품은?"),
    MANAGEMENT_SUPPORT_HEAD("경영지원팀 팀장은 누구야?"),
    IN_PROGRESS_PROJECT_LEADERS("진행 중인 프로젝트를 이끄는 직원 목록"),
    PRODUCT_S1_ISSUES("Product-S1 관련 고객 이슈 현황은?"),
    MOST_ACCOUNTS_MANAGERS("가장 많은 고객을 담당하는 직원은?");

    private final String text;

    GraphQuestion(String text) {
        this.text = text;
    }

    public String text() {
        return text;
    }

    static GraphQuestion fromText(String text) {
        for (GraphQuestion question : values()) {
            if (question.text.equals(text)) {
                return question;
            }
        }
        throw new IllegalArgumentException("지원하지 않는 공식 knowledge graph 문항입니다: " + text);
    }
}
