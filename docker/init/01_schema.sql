-- DSPAtlas / DynaProt schema
-- Applied automatically when the MySQL container starts for the first time.

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

CREATE TABLE IF NOT EXISTS dynaprot_experiment (
    dynaprot_experiment VARCHAR(11) PRIMARY KEY,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    perturbation VARCHAR(255),
    `condition` VARCHAR(225),
    taxonomy_id INT,
    strain VARCHAR(255),
    instrument VARCHAR(255),
    number_of_lip_files INT,
    number_of_tr_files INT,
    experiment VARCHAR(255),
    approach VARCHAR(255),
    reference_for_protocol VARCHAR(255),
    data_analysis VARCHAR(255),
    publication LONGTEXT,
    doi VARCHAR(255),
    search_settings VARCHAR(255),
    fasta VARCHAR(255),
    data_re_analysis_settings VARCHAR(255),
    path_to_raw_files VARCHAR(255),
    digestion_protocol VARCHAR(255),
    e_s_ratio VARCHAR(255),
    pk_digestion_time_in_sec INT,
    protease VARCHAR(255),
    author VARCHAR(255),
    input_file VARCHAR(255),
    qc_pdf_file LONGBLOB
);

CREATE TABLE IF NOT EXISTS dynaprot_experiment_comparison (
    dpx_comparison VARCHAR(20) PRIMARY KEY,
    taxonomy_id INT,
    `condition` VARCHAR(225),
    dose VARCHAR(255),
    dynaprot_experiment VARCHAR(11),
    FOREIGN KEY (dynaprot_experiment) REFERENCES dynaprot_experiment(dynaprot_experiment)
);

CREATE TABLE IF NOT EXISTS differential_abundance (
    differential_abundance_id INT AUTO_INCREMENT PRIMARY KEY,
    dpx_comparison VARCHAR(20),
    pg_protein_accessions VARCHAR(255),
    pep_grouping_key VARCHAR(255),
    pos_start INT,
    pos_end INT,
    diff FLOAT,
    adj_pval FLOAT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison)
);

CREATE TABLE IF NOT EXISTS protein_scores (
    protein_score_id INT AUTO_INCREMENT PRIMARY KEY,
    pg_protein_accessions VARCHAR(255),
    protein_description TEXT,
    cumulativeScore FLOAT,
    dpx_comparison VARCHAR(20),
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison)
);

CREATE TABLE IF NOT EXISTS go_term (
    go_term_entry_id INT AUTO_INCREMENT PRIMARY KEY,
    go_id VARCHAR(255),
    go_term TEXT,
    accessions TEXT,
    taxonomy_id INT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (taxonomy_id) REFERENCES organism(taxonomy_id)
);

CREATE TABLE IF NOT EXISTS go_analysis (
    go_analysis_id INT AUTO_INCREMENT PRIMARY KEY,
    dpx_comparison VARCHAR(20),
    go_id VARCHAR(255),
    term VARCHAR(255),
    pval FLOAT,
    adj_pval FLOAT,
    n_detected_proteins INT,
    n_detected_proteins_in_process INT,
    n_significant_proteins INT,
    n_significant_proteins_in_process INT,
    n_proteins_expected FLOAT,
    enrichment_type VARCHAR(255),
    go_type VARCHAR(10),
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison)
);

-- Seed organisms
INSERT IGNORE INTO organism (taxonomy_id, organism_name) VALUES
    (9606,   'Homo sapiens'),
    (10090,  'Mus musculus'),
    (559292, 'Saccharomyces cerevisiae'),
    (83333,  'Escherichia coli K-12'),
    (562,    'Escherichia coli');
