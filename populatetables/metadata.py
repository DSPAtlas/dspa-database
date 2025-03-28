import os
import pandas as pd
import mysql.connector
import math
import yaml

# -------------------------------------------------------------------------------------
# Upload Experiment and comparisons
# Differential Abundance
# GO Term
# -------------------------------------------------------------------------------------

db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    database="dynaprotdbv2",
)
cursor = db_connection.cursor()

def replace_missing(data, default=None):
    if data is None or data == "" or (isinstance(data, float) and math.isnan(data)):
        return default
    return data

def generate_next_id(table, column, prefix):
    cursor.execute(f"SELECT MAX({column}) FROM {table}")
    result = cursor.fetchone()[0]
    if result:
        num = int(result.replace(prefix, "")) + 1
    else:
        num = 1
    return f"{prefix}{num:06d}"

base_directory = "data/experiments"

for folder in os.listdir(base_directory):
    folder_path = os.path.join(base_directory, folder)
    if not os.path.isdir(folder_path):
        continue

    params_file = os.path.join(folder_path, "params.yaml")
    pdf_path = os.path.join(folder_path, "qc_plots.pdf")
    pdf_data = None
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()

    if os.path.exists(params_file):
        with open(params_file, "r") as file:
            params_data = yaml.safe_load(file)

        dpx_id = generate_next_id("dynaprot_experiment", "dynaprot_experiment", "DPX")

        sql = """
        INSERT INTO dynaprot_experiment (
            dynaprot_experiment, perturbation, `condition`, taxonomy_id, strain,
            instrument, number_of_lip_files, number_of_tr_files, experiment,
            approach, reference_for_protocol, data_analysis, publication, doi,
            search_settings, fasta, data_re_analysis_settings, path_to_raw_files,
            digestion_protocol, e_s_ratio, pk_digestion_time_in_sec, protease,
            author, input_file, qc_pdf_file
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            dpx_id,
            replace_missing(params_data.get("perturbation")),
            replace_missing(params_data.get("condition")),
            int(params_data.get("taxonomy_id", 0)),
            replace_missing(params_data.get("strain")),
            replace_missing(params_data.get("instrument")),
            int(params_data.get("n_files", 0)),
            int(params_data.get("n_files_trp", 0)),
            replace_missing(params_data.get("experiment")),
            replace_missing(params_data.get("approach")),
            replace_missing(params_data.get("reference_to_protocol")),
            replace_missing(params_data.get("data_analysis")),
            replace_missing(params_data.get("publication")),
            replace_missing(params_data.get("doi")),
            replace_missing(params_data.get("search_settings")),
            replace_missing(params_data.get("fasta")),
            replace_missing(params_data.get("data_reanalysis_settings")),
            replace_missing(params_data.get("path_to_raw_files")),
            replace_missing(params_data.get("digestion_protocol")),
            replace_missing(params_data.get("e_s_ratio")),
            replace_missing(params_data.get("pk_digestion_time")),
            replace_missing(params_data.get("protease")),
            replace_missing(params_data.get("author")),
            replace_missing(params_data.get("input_file")),
            pdf_data
        )
        cursor.execute(sql, values)

        dpx_comparisons = params_data.get("dpx_comparison", [])
        comparison_names = params_data.get("comparison", [])

        for i, comp_id in enumerate(dpx_comparisons):
            comparison_name = comparison_names[i]

            dpx_comp_id = dpx_id + "-" +comp_id
            sql = """
            INSERT INTO dynaprot_experiment_comparison (
                dpx_comparison, taxonomy_id, `condition`, dose, dynaprot_experiment
            ) VALUES (%s, %s, %s, %s, %s)
            """
            values = (
                dpx_comp_id,
                int(params_data.get("taxonomy_id", 0)),
                replace_missing(params_data.get("condition")),
                comparison_name,
                dpx_id
            )
            cursor.execute(sql, values)

            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)

                if file_name == f"differential_abundance_{comp_id}_{comparison_name}.csv":
                    df = pd.read_csv(file_path, delimiter="\t")
                    df = df.where(pd.notnull(df), None)
                    df = df.rename(columns={'start': 'pos_start', 'end': 'pos_end'})
                    columns = ['pg_protein_accessions', 'eg_modified_peptide', 'pos_start', 'pos_end', 'diff', 'adj_pval']
                    df = df[columns]
                    for _, row in df.iterrows():
                        sql = """
                        INSERT INTO differential_abundance (
                            dpx_comparison, pg_protein_accessions, pep_grouping_key,
                            pos_start, pos_end, diff, adj_pval
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        values = (
                            dpx_comp_id,
                            replace_missing(row.get('pg_protein_accessions')),
                            replace_missing(row.get('eg_modified_peptide')),
                            replace_missing(row.get('pos_start')),
                            replace_missing(row.get('pos_end')),
                            replace_missing(row.get('diff')),
                            replace_missing(row.get('adj_pval')),
                        )
                        cursor.execute(sql, values)

                if file_name == f"go_term_{comp_id}_{comparison_name}.csv":
                    df = pd.read_csv(file_path, delimiter="\t")
                    df = df.where(pd.notnull(df), None)
                    columns = ['term', 'go_id', 'pval', 'adj_pval',
                               'n_detected_proteins', 'n_detected_proteins_in_process',
                               'n_significant_proteins', 'n_significant_proteins_in_process',
                               'enrichment_type']
                    df = df[columns]
                    for _, row in df.iterrows():
                        sql = """
                        INSERT INTO go_analysis (
                            dpx_comparison, term, go_id, pval, adj_pval,
                            n_detected_proteins, n_detected_proteins_in_process,
                            n_significant_proteins, n_significant_proteins_in_process,
                            enrichment_type
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        values = (
                            dpx_comp_id,
                            replace_missing(row.get('term')),
                            replace_missing(row.get('go_id')),
                            replace_missing(row.get('pval')),
                            replace_missing(row.get('adj_pval')),
                            replace_missing(row.get('n_detected_proteins')),
                            replace_missing(row.get('n_detected_proteins_in_process')),
                            replace_missing(row.get('n_significant_proteins')),
                            replace_missing(row.get('n_significant_proteins_in_process')),
                            replace_missing(row.get('enrichment_type')),
                        )
                        cursor.execute(sql, values)

# Commit and close
db_connection.commit()
cursor.close()
db_connection.close()

print("Data upload complete.")
