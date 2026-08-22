package io.companyx.ontology.prototype.graphcomparison;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;
import java.util.Set;

/** Validates the supplied JSON graph before either engine projects it. */
final class OfficialGraphSourceValidator {
    private static final Set<String> NODE_TYPES =
            Set.of("client", "product", "employee", "project", "department");
    private static final Map<String, EndpointTypes> ENDPOINT_TYPES = Map.of(
            "BELONGS_TO", new EndpointTypes("employee", "department"),
            "HEAD_IS", new EndpointTypes("department", "employee"),
            "USES", new EndpointTypes("client", "product"),
            "MANAGES_ACCOUNT", new EndpointTypes("employee", "client"),
            "HAS_PROJECT", new EndpointTypes("client", "project"),
            "LEADS", new EndpointTypes("employee", "project"),
            "REPORTED_ISSUE", new EndpointTypes("client", "product"));
    private static final Set<String> INTEGER_EDGE_PROPERTIES =
            Set.of("amount", "contract_id", "ticket_id");
    private static final Set<String> TEXT_EDGE_PROPERTIES = Set.of("priority", "status");

    private OfficialGraphSourceValidator() {}

    static void requireValid(JsonNode nodes, JsonNode edges) {
        requireArray(nodes, "nodes.json");
        requireArray(edges, "edges.json");

        Map<String, String> nodeTypes = new java.util.HashMap<>();
        int nodeIndex = 0;
        for (JsonNode node : nodes) {
            String locator = "graph/nodes.json#index=" + nodeIndex;
            String id = requireText(node, "id", locator);
            String type = requireText(node, "type", locator);
            requireText(node, "name", locator);
            if (!NODE_TYPES.contains(type)) {
                throw new IllegalArgumentException("unknown node type: " + locator);
            }
            validatePropertyValues(node.path("properties"), "node", locator);
            if (nodeTypes.putIfAbsent(id, type) != null) {
                throw new IllegalArgumentException("duplicate node source ID: " + id);
            }
            nodeIndex++;
        }

        int edgeIndex = 0;
        for (JsonNode edge : edges) {
            String locator = "graph/edges.json#index=" + edgeIndex;
            String source = requireText(edge, "source", locator);
            String target = requireText(edge, "target", locator);
            String relation = requireText(edge, "relation", locator);
            String sourceType = nodeTypes.get(source);
            String targetType = nodeTypes.get(target);
            if (sourceType == null || targetType == null) {
                throw new IllegalArgumentException(
                        "relation endpoint must reference an existing node: " + locator);
            }
            EndpointTypes expected = ENDPOINT_TYPES.get(relation);
            if (expected == null
                    || !expected.sourceType().equals(sourceType)
                    || !expected.targetType().equals(targetType)) {
                throw new IllegalArgumentException(
                        "relation endpoints must match schema: " + locator);
            }
            validateEdgeProperties(edge.path("properties"), relation, locator);
            edgeIndex++;
        }
    }

    private static void validateEdgeProperties(JsonNode properties, String relation, String locator) {
        if (properties.isMissingNode()) {
            if ("USES".equals(relation)) {
                throw new IllegalArgumentException("USES relation requires contract_id: " + locator);
            }
            return;
        }
        if (!properties.isObject()) {
            throw new IllegalArgumentException("edge properties must be an object: " + locator);
        }
        validatePropertyValues(properties, "edge", locator);
        if ("USES".equals(relation) && !properties.has("contract_id")) {
            throw new IllegalArgumentException("USES relation requires contract_id: " + locator);
        }
        properties.properties().forEach(entry -> {
            String key = entry.getKey();
            JsonNode value = entry.getValue();
            if (INTEGER_EDGE_PROPERTIES.contains(key) && !value.isIntegralNumber()) {
                throw new IllegalArgumentException(
                        "edge property must be an integer: " + key + " at " + locator);
            }
            if (TEXT_EDGE_PROPERTIES.contains(key) && !value.isTextual()) {
                throw new IllegalArgumentException(
                        "edge property must be text: " + key + " at " + locator);
            }
        });
    }

    private static void validatePropertyValues(JsonNode properties, String owner, String locator) {
        if (properties.isMissingNode()) {
            return;
        }
        if (!properties.isObject()) {
            throw new IllegalArgumentException(owner + " properties must be an object: " + locator);
        }
        properties.properties().forEach(entry -> {
            JsonNode value = entry.getValue();
            if (!value.isTextual()
                    && !value.isIntegralNumber()
                    && !value.isFloatingPointNumber()
                    && !value.isBoolean()) {
                throw new IllegalArgumentException(
                        owner
                                + " property must be a scalar supported by the RDF projection: "
                                + entry.getKey()
                                + " at "
                                + locator);
            }
        });
    }

    private static void requireArray(JsonNode value, String filename) {
        if (!value.isArray()) {
            throw new IllegalArgumentException(filename + " must contain a JSON array");
        }
    }

    private static String requireText(JsonNode object, String field, String locator) {
        JsonNode value = object.path(field);
        if (!value.isTextual() || value.textValue().isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank text: " + locator);
        }
        return value.textValue();
    }

    private record EndpointTypes(String sourceType, String targetType) {}
}
