-- Supports taxonomy-scoped protein lookups and taxonomy-aware joins on protein_name.
CREATE INDEX idx_ope_taxonomy_protein ON organism_proteome_entries (taxonomy_id, protein_name);

-- Supports joins and existence checks that match proteins by protein_name alone.
CREATE INDEX idx_ope_protein_name ON organism_proteome_entries (protein_name);

-- Avoids full scans and filesorts when fetching all peptides for one accession ordered by position.
CREATE INDEX idx_da_accession_pos ON differential_abundance (pg_protein_accessions, pos_start);

-- Helps experiment-level differential abundance filtering by comparison and adjusted p-value, with diff available in the index.
CREATE INDEX idx_da_comparison_adj_diff ON differential_abundance (dpx_comparison, adj_pval, diff);

-- Supports comparison-plus-accession lookups that also need peptide ordering by pos_start.
CREATE INDEX idx_da_comparison_accession_pos ON differential_abundance (dpx_comparison, pg_protein_accessions, pos_start);

-- Speeds joins from dynaprot experiment to comparison rows while keeping taxonomy available for follow-up joins.
CREATE INDEX idx_dec_experiment_comparison_tax ON dynaprot_experiment_comparison (dynaprot_experiment, dpx_comparison, taxonomy_id);

-- Supports condition filters, optional taxonomy filters, and downstream access to comparison ids.
CREATE INDEX idx_dec_condition_tax_comparison ON dynaprot_experiment_comparison (`condition`, taxonomy_id, dpx_comparison);

-- Speeds GO analysis lookups keyed by comparison and subsequent joins to GO terms.
CREATE INDEX idx_ga_comparison_go ON go_analysis (dpx_comparison, go_id);

-- Supports joins from go_analysis into go_term by go_id.
CREATE INDEX idx_go_id ON go_term (go_id);

-- Supports taxonomy-aware GO term joins so the correct species-specific term rows are found quickly.
CREATE INDEX idx_gt_go_tax ON go_term (go_id, taxonomy_id);

-- Supports experiment-level protein score queries that also sort or cover cumulativeScore.
CREATE INDEX idx_ps_dpx_protein_score ON protein_scores (dpx_comparison, pg_protein_accessions, cumulativeScore);

-- Supports comparison-plus-protein score joins without depending on the wider covering index.
CREATE INDEX idx_ps_comparison_accession ON protein_scores (dpx_comparison, pg_protein_accessions);

-- Speeds dose-response lookups by experiment and protein, then narrows to peptide grouping keys.
CREATE INDEX idx_drf_experiment_accession_pep ON dose_response_fit (dynaprot_experiment, pg_protein_accessions, pep_grouping_key);

-- Speeds retrieval of fitted dose-response curves for the peptide keys of one experiment.
CREATE INDEX idx_drpc_experiment_pep ON dose_response_plot_curve (dynaprot_experiment, pep_grouping_key);

-- Speeds retrieval of dose-response plot points for the peptide keys of one experiment.
CREATE INDEX idx_drpp_experiment_pep ON dose_response_plot_points (dynaprot_experiment, pep_grouping_key);

