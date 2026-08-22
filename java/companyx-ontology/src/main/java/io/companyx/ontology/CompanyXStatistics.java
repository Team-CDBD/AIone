package io.companyx.ontology;

import java.util.HashSet;
import java.util.Set;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.ResIterator;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.RDF;

public final class CompanyXStatistics {
    public ProjectionStatistics summarize(Model model) {
        RecordCounts contracts = countRecords(
                model,
                CompanyXVocabulary.CONTRACT,
                CompanyXVocabulary.CONTRACT_CLIENT,
                CompanyXVocabulary.CONTRACT_PRODUCT);
        RecordCounts tickets = countRecords(
                model,
                CompanyXVocabulary.SUPPORT_TICKET,
                CompanyXVocabulary.TICKET_CLIENT,
                CompanyXVocabulary.TICKET_PRODUCT);

        return new ProjectionStatistics(
                contracts.instances(),
                contracts.pairs(),
                tickets.instances(),
                tickets.pairs(),
                model.size());
    }

    private static RecordCounts countRecords(
            Model model, Resource recordType, Property clientProperty, Property productProperty) {
        int instances = 0;
        Set<ResourcePair> pairs = new HashSet<>();
        ResIterator records = model.listResourcesWithProperty(RDF.type, recordType);
        try {
            while (records.hasNext()) {
                Resource record = records.nextResource();
                Resource client = record.getRequiredProperty(clientProperty).getResource();
                Resource product = record.getRequiredProperty(productProperty).getResource();
                instances++;
                pairs.add(new ResourcePair(client.getURI(), product.getURI()));
            }
        } finally {
            records.close();
        }
        return new RecordCounts(instances, pairs.size());
    }

    private record RecordCounts(int instances, int pairs) {}

    private record ResourcePair(String clientIri, String productIri) {}
}

