CREATE TABLE IF NOT EXISTS organism (
    taxonomy_id INT PRIMARY KEY,
    organism_name VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS organism_proteome (
    proteome_id VARCHAR(20) PRIMARY KEY,
    taxonomy_id INT,
    FOREIGN KEY (taxonomy_id) REFERENCES organism(taxonomy_id)
);

CREATE TABLE IF NOT EXISTS organism_proteome_entries (
    proteome_id VARCHAR(20),
    taxonomy_id INT,
    seq_id VARCHAR(255), 
    seq TEXT,
    protein_name VARCHAR(255),
    protein_description VARCHAR(255),
    gene_name VARCHAR(255),
    FOREIGN KEY (taxonomy_id) REFERENCES organism(taxonomy_id),
    PRIMARY KEY (proteome_id, seq_id)
);

INSERT INTO organism (taxonomy_id, organism_name) VALUES
    (9606, 'Homo sapiens'),
    (10090, 'Mus musculus'),
    (559292, 'Saccharomyces cerevisiae'),
    (83333, 'Escherichia coli');


