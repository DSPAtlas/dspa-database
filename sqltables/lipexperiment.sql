
-- ALTER TABLE differential_abundance DROP FOREIGN KEY differential_abundance_ibfk_1;
-- ALTER TABLE organism_proteome DROP FOREIGN KEY organism_proteome_ibfk_1;

CREATE TABLE IF NOT EXISTS dynaprot_experiment (
    dynaprot_experiment VARCHAR(11) PRIMARY KEY,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    perturbation VARCHAR(255),
    `condition`  VARCHAR(225),
    taxonomy_id INT,
    strain VARCHAR(255),
    instrument VARCHAR(255),
    number_of_lip_files INT,
    number_of_tr_files INT,
    experiment VARCHAR(255), 
    approach VARCHAR(255),
    reference_for_protocol VARCHAR(255),
    data_analysis VARCHAR(255),
    publication TEXT,
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

ALTER TABLE dynaprot_experiment 
MODIFY publication LONGTEXT;

CREATE TABLE IF NOT EXISTS dynaprot_experiment_comparison (
    dpx_comparison VARCHAR(11) PRIMARY KEY,
    taxonomy_id INT,
     `condition`  VARCHAR(225),
    dose VARCHAR(255),
    dynaprot_experiment VARCHAR(11),
    FOREIGN KEY (dynaprot_experiment) REFERENCES dynaprot_experiment(dynaprot_experiment)
);

CREATE TABLE IF NOT EXISTS differential_abundance (
    differential_abundance_id INT AUTO_INCREMENT,
    dpx_comparison VARCHAR(11),
    pg_protein_accessions VARCHAR(255),
    pep_grouping_key VARCHAR(255),
    pos_start INT,
    pos_end INT,
    diff FLOAT,
    adj_pval FLOAT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison),
    PRIMARY KEY (differential_abundance_id)
);



CREATE TABLE IF NOT EXISTS protein_scores (
    protein_score_id INT AUTO_INCREMENT PRIMARY KEY,
    pg_protein_accessions VARCHAR(255),
    protein_description TEXT,
    cumulativeScore FLOAT,
    dpx_comparison VARCHAR(11),
    FOREIGN KEY (dpx_comparison) REFERENCES dynaprot_experiment_comparison(dpx_comparison)
);
