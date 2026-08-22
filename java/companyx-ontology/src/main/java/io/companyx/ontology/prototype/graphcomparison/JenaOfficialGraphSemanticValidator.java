package io.companyx.ontology.prototype.graphcomparison;

import java.io.InputStream;
import java.io.StringWriter;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.shacl.ShaclValidator;
import org.apache.jena.shacl.Shapes;

/** PROTOTYPE ONLY: SHACL gate for the supplied official JSON graph projection. */
final class JenaOfficialGraphSemanticValidator {
    private static final String SHAPES_RESOURCE =
            "/io/companyx/ontology/prototype/graphcomparison/official-graph-shapes.ttl";

    private JenaOfficialGraphSemanticValidator() {}

    static void requireValid(Model model) {
        var report = ShaclValidator.get().validate(loadShapes(), model.getGraph());
        if (report.conforms()) {
            return;
        }
        StringWriter serialized = new StringWriter();
        RDFDataMgr.write(serialized, report.getModel(), Lang.TURTLE);
        throw new IllegalArgumentException(
                "Company-X official graph failed Jena SHACL validation:\n" + serialized);
    }

    private static Shapes loadShapes() {
        Model shapesModel = ModelFactory.createDefaultModel();
        try (InputStream input = JenaOfficialGraphSemanticValidator.class
                .getResourceAsStream(SHAPES_RESOURCE)) {
            if (input == null) {
                throw new IllegalStateException("SHACL resource를 찾지 못했습니다: " + SHAPES_RESOURCE);
            }
            RDFDataMgr.read(shapesModel, input, Lang.TURTLE);
            return Shapes.parse(shapesModel);
        } catch (java.io.IOException error) {
            throw new IllegalStateException("SHACL resource를 읽지 못했습니다", error);
        } finally {
            shapesModel.close();
        }
    }
}
