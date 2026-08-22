package io.companyx.ontology;

import java.io.IOException;
import java.io.InputStream;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.shacl.ShaclValidator;
import org.apache.jena.shacl.Shapes;
import org.apache.jena.shacl.ValidationReport;

public final class CompanyXValidator {
    private final Shapes shapes;

    public CompanyXValidator(Path shapesPath) throws IOException {
        Path normalizedShapes = shapesPath.toAbsolutePath().normalize();
        if (!Files.isRegularFile(normalizedShapes)) {
            throw new IOException("Company-X SHACL shapes를 찾지 못했습니다: " + normalizedShapes);
        }

        shapes = loadShapes(normalizedShapes);
    }

    public CompanyXValidationResult validate(Model dataModel) {
        ValidationReport report = ShaclValidator.get().validate(shapes, dataModel.getGraph());
        StringWriter serialized = new StringWriter();
        RDFDataMgr.write(serialized, report.getModel(), Lang.TURTLE);
        return new CompanyXValidationResult(
                report.conforms(), report.getEntries().size(), serialized.toString());
    }

    private static Shapes loadShapes(Path shapesPath) throws IOException {
        Model shapesModel = ModelFactory.createDefaultModel();
        try {
            try (InputStream input = Files.newInputStream(shapesPath)) {
                RDFDataMgr.read(shapesModel, input, Lang.TURTLE);
            }
            return Shapes.parse(shapesModel);
        } finally {
            shapesModel.close();
        }
    }
}
