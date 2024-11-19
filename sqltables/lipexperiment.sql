
-- ALTER TABLE differential_abundance DROP FOREIGN KEY differential_abundance_ibfk_1;
-- ALTER TABLE organism_proteome DROP FOREIGN KEY organism_proteome_ibfk_1;


-- DROP TABLE IF EXISTS lip_experiments;
CREATE TABLE IF NOT EXISTS lip_experiments (
    lipexperiment_id VARCHAR(10) PRIMARY KEY,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    perturbation VARCHAR(255),
    condition VARCHAR(225),
    taxonomy_id INT,
    strain VARCHAR(255),
    instrument VARCHAR(255),
    number_of_lip_files INT,
    numer_of_tr_files INT,
    experiment VARCHAR(255),
    approach VARCHAR(255),
    reference_for_protocol VARCHAR(255),
    data_analysis VARCHAR(255),
    publication VARCHAR(255),
    doi VARCHAR(255),
    search_settings VARCHAR(255),
    fasta INT,
    data_re_analysis_settings VARCHAR(255),
    path_to_raw_files VARCHAR(255),
    digestion_protocol VARCHAR(255),
    e_s_ratio VARCHAR(255),
    pk_digestion_time VARCHAR(255),
    protease VARCHAR(255),
    author VARCHAR(255)
);

-- DROP TABLE IF EXISTS differential_abundance;
CREATE TABLE IF NOT EXISTS differential_abundance (
    differential_abundance_id INT AUTO_INCREMENT,
    lipexperiment_id VARCHAR(10),
    pg_protein_accessions VARCHAR(255),
    pep_grouping_key VARCHAR(255),
    pos_start INT,
    pos_end INT,
    diff FLOAT,
    adj_pval FLOAT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Add other columns as needed
    FOREIGN KEY (lipexperiment_id) REFERENCES lip_experiments(lipexperiment_id),
    PRIMARY KEY (differential_abundance_id)
);


CREATE TABLE IF NOT EXISTS experiment_group (
    group_id VARCHAR(10) PRIMARY KEY,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 
