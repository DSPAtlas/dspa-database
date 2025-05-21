CREATE TABLE IF NOT EXISTS go_analysis (
    go_analysis_id INT AUTO_INCREMENT,
    dpx_comparison VARCHAR(11),
    go_id VARCHAR(255),
    term VARCHAR(255),
    pval FLOAT,
    adj_pval FLOAT,
    n_detected_proteins INT,
    n_detected_proteins_in_process INT,
    n_significant_proteins INT,
    n_significant_proteins_in_process INT,
    enrichment_type VARCHAR(255),
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison),
    PRIMARY KEY (go_analysis_id)
);

CREATE TABLE IF NOT EXISTS go_term (
    go_term_entry_id INT AUTO_INCREMENT,
    go_id VARCHAR(255),
    go_term  TEXT,
    accessions TEXT,
    taxonomy_id INT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (taxonomy_id) REFERENCES organism(taxonomy_id),
    PRIMARY KEY (go_term_entry_id)
);

