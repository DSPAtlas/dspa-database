-- DROP TABLE IF EXISTS differential_abundance;
CREATE TABLE IF NOT EXISTS go_analysis (
    go_analysis_id INT AUTO_INCREMENT,
    lipexperiment_id VARCHAR(10),
    go_id VARCHAR(255),
    term VARCHAR(255),
    pval FLOAT,
    adj_pval FLOAT,
    n_detected_proteins INT,
    n_detected_proteins_in_process INT,
    n_significant_proteins INT,
    n_significant_proteins_in_process INT,
    enrichment_type VARCHAR(255),
    -- Add other columns as needed
    FOREIGN KEY (lipexperiment_id) REFERENCES lip_experiments(lipexperiment_id),
    PRIMARY KEY (go_analysis_id)
);
