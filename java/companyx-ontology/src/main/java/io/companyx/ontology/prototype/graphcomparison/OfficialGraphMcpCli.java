package io.companyx.ontology.prototype.graphcomparison;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/** Executes one official graph question and writes its answer plus source locators as JSON. */
public final class OfficialGraphMcpCli {
    private static final ObjectMapper JSON = new ObjectMapper();

    private OfficialGraphMcpCli() {}

    public static void main(String[] args) throws Exception {
        Path datasetDirectory = Path.of(requiredProperty("companyx.dataset"));
        if (args.length > 1 || (args.length == 1 && !"--stdio".equals(args[0]))) {
            throw new IllegalArgumentException("usage: OfficialGraphMcpCli [--stdio]");
        }
        try (GraphTool tool = JenaGraphTool.load(datasetDirectory.resolve("graph"))) {
            if (args.length == 1) {
                OfficialGraphQuestionCatalog.requireValid(datasetDirectory);
                serve(tool);
                return;
            }
            String questionText = requiredProperty("companyx.question");
            GraphQuestion question = OfficialGraphQuestionCatalog.resolve(datasetDirectory, questionText);
            JSON.writeValue(System.out, response(question, tool.query(new GraphQuery(question))));
        }
    }

    private static void serve(GraphTool tool) throws Exception {
        try (BufferedReader input = new BufferedReader(
                        new InputStreamReader(System.in, StandardCharsets.UTF_8));
                BufferedWriter output = new BufferedWriter(
                        new OutputStreamWriter(System.out, StandardCharsets.UTF_8))) {
            String questionText;
            while ((questionText = input.readLine()) != null) {
                try {
                    GraphQuestion question = GraphQuestion.fromText(questionText);
                    output.write(JSON.writeValueAsString(
                            response(question, tool.query(new GraphQuery(question)))));
                } catch (IllegalArgumentException error) {
                    output.write(JSON.writeValueAsString(Map.of("error", error.getMessage())));
                }
                output.newLine();
                output.flush();
            }
        }
    }

    private static OfficialGraphMcpResponse response(GraphQuestion question, GraphOperationResult result) {
        List<OfficialGraphMcpAnswer> answers = result.answers().stream()
                .map(answer -> new OfficialGraphMcpAnswer(
                        answer.id(), answer.name(), answer.details(), answer.sourceIds()))
                .toList();
        GraphEvidenceContext context = result.evidenceContext();
        return new OfficialGraphMcpResponse(
                question.text(),
                question.name(),
                result.engine(),
                result.queryLanguage(),
                result.executedQuery(),
                answers,
                new OfficialGraphMcpEvidenceContext(
                        context.answerDataRole(), context.evidenceRole()));
    }

    private static String requiredProperty(String name) {
        String value = System.getProperty(name);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("required system property is missing: " + name);
        }
        return value;
    }

    private record OfficialGraphMcpResponse(
            String question,
            String questionId,
            String engine,
            String queryLanguage,
            String executedQuery,
            List<OfficialGraphMcpAnswer> answers,
            OfficialGraphMcpEvidenceContext evidenceContext) {}

    private record OfficialGraphMcpAnswer(
            String id, String name, Map<String, String> details, List<String> sourceLocators) {}

    private record OfficialGraphMcpEvidenceContext(String answerDataRole, String evidenceRole) {}
}
