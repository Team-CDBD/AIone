package io.companyx.ontology;

import java.nio.file.Path;
import java.util.List;

public record CompanyXSourceData(
        Path datasetDirectory,
        List<ClientRow> clients,
        List<ProductRow> products,
        List<ContractRow> contracts,
        List<SupportTicketRow> supportTickets) {

    public CompanyXSourceData {
        datasetDirectory = datasetDirectory.toAbsolutePath().normalize();
        clients = List.copyOf(clients);
        products = List.copyOf(products);
        contracts = List.copyOf(contracts);
        supportTickets = List.copyOf(supportTickets);
    }
}

