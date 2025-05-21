CREATE TABLE IF NOT EXISTS dose_response_fit (
    dose_response_id INT AUTO_INCREMENT,
    dynaprot_experiment VARCHAR(11),
    pg_protein_accessions VARCHAR(255),
    pep_grouping_key VARCHAR(255),
    `rank` INT,
    hill_coefficient FLOAT,
    min_model FLOAT,
    max_model FLOAT,
    ec_50 FLOAT, 
    correlation FLOAT,
    pval FLOAT,
    enough_conditions BOOLEAN,
    dose_MNAR BOOLEAN,
    anova_pval FLOAT,
    anova_adj_pval FLOAT,
    passed_filter BOOLEAN,
    score FLOAT,
    FOREIGN KEY (dynaprot_experiment) REFERENCES dynaprot_experiment(dynaprot_experiment),
    PRIMARY KEY (dose_response_id)
);

CREATE TABLE IF NOT EXISTS dose_response_plot_curve (
    dose_response_plot_curve_id INT AUTO_INCREMENT,
    dynaprot_experiment VARCHAR(11),
    pep_grouping_key VARCHAR(255),
    dose FLOAT,
    prediction FLOAT,
    lower FLOAT,
    upper FLOAT,
    FOREIGN KEY (dynaprot_experiment) REFERENCES dynaprot_experiment(dynaprot_experiment),
    PRIMARY KEY (dose_response_plot_curve_id)
);

CREATE TABLE IF NOT EXISTS dose_response_plot_points (
    dose_response_plot_points_id  INT AUTO_INCREMENT,
    dynaprot_experiment VARCHAR(11),
    pep_grouping_key VARCHAR(255),
    normalised_intensity_log2 FLOAT,
    dose FLOAT,
    FOREIGN KEY (dynaprot_experiment) REFERENCES dynaprot_experiment(dynaprot_experiment),
    PRIMARY KEY (dose_response_plot_points_id)
);