import os
import pandas as pd
import mysql.connector

# MySQL connection details
mysql_user = os.environ.get('MYSQL_USER', 'root')
mysql_password = os.environ.get('MYSQL_PASSWORD', 'your_password')
mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
mysql_database = os.environ.get('MYSQL_DATABASE', 'dspadb')

# Create a MySQL connection
db_connection = mysql.connector.connect(
    host=mysql_host,
    user=mysql_user,
    password=mysql_password,
    database=mysql_database,
)
cursor = db_connection.cursor()

# Function to replace missing values with "NA"
def replace_missing(data, default="NA"):
    return data if data is not None and data != "" else default

# Path to the base directory containing experiment folders
base_directory = "data/preprocessed/"

# Iterate through folders in the base directory
for folder in os.listdir(base_directory):
    folder_path = os.path.join(base_directory, folder)
    if not os.path.isdir(folder_path):
        continue

    # Parse params file
    params_file = os.path.join(folder_path, "params_GRP00005.yaml")
    if os.path.exists(params_file):
        with open(params_file, "r") as file:
            params_data = {}
            for line in file:
                key, value = line.strip().split(": ", 1)
                params_data[key] = value.strip('"')

        # Insert data into lip_experiments table
        experiment_ids = eval(params_data.get("experiment_id", "[]"))  # Convert string to list
        for experiment_id in experiment_ids:
            sql = """
            INSERT INTO lip_experiments (
                lipexperiment_id, perturbation, condition, taxonomy_id, strain,
                instrument, number_of_lip_files, numer_of_tr_files, experiment,
                approach, reference_for_protocol, data_analysis, publication, doi,
                search_settings, fasta, data_re_analysis_settings, path_to_raw_files,
                digestion_protocol, e_s_ratio, pk_digestion_time, protease, author
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                replace_missing(experiment_id),
                replace_missing(params_data.get("treatment")),
                replace_missing(params_data.get("ref_condition")),
                int(params_data.get("taxonomy_id", 0)),
                replace_missing(params_data.get("strain")),
                replace_missing(params_data.get("instrument")),
                int(params_data.get("number_of_lip_files", 0)),
                int(params_data.get("number_of_tr_files", 0)),
                replace_missing(params_data.get("experiment")),
                replace_missing(params_data.get("approach")),
                replace_missing(params_data.get("reference_for_protocol")),
                replace_missing(params_data.get("data_analysis")),
                replace_missing(params_data.get("publication")),
                replace_missing(params_data.get("doi")),
                replace_missing(params_data.get("search_settings")),
                int(params_data.get("fasta", 0)),
                replace_missing(params_data.get("data_re_analysis_settings")),
                replace_missing(params_data.get("path_to_raw_files")),
                replace_missing(params_data.get("digestion_protocol")),
                replace_missing(params_data.get("e_s_ratio")),
                replace_missing(params_data.get("pk_digestion_time")),
                replace_missing(params_data.get("protease")),
                replace_missing(params_data.get("author")),
            )
            cursor.execute(sql, values)

        # Insert data into experiment_group table
        sql = "INSERT INTO experiment_group (group_id) VALUES (%s)"
        cursor.execute(sql, (replace_missing(params_data.get("group_id")),))

    # Process other files in the folder
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".csv"):
            file_path = os.path.join(folder_path, file_name)
            if "differential_abundance" in file_name:
                # Process differential_abundance files
                df = pd.read_csv(file_path)
                df['lipexperiment_id'] = replace_missing(file_name.split("_")[2])
                columns_to_keep = ['lipexperiment_id', 'pg_protein_accessions', 'pep_grouping_key', 'pos_start', 'pos_end', 'diff', 'adj_pval']
                df = df.rename(columns={'start': 'pos_start', 'end': 'pos_end', "pep_stripped_sequence": "pep_grouping_key"})
                df = df[columns_to_keep]

                for _, row in df.iterrows():
                    sql = """
                    INSERT INTO differential_abundance (
                        lipexperiment_id, pg_protein_accessions, pep_grouping_key,
                        pos_start, pos_end, diff, adj_pval
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        replace_missing(row.get('lipexperiment_id')),
                        replace_missing(row.get('pg_protein_accessions')),
                        replace_missing(row.get('pep_grouping_key')),
                        replace_missing(row.get('pos_start', 0)),
                        replace_missing(row.get('pos_end', 0)),
                        replace_missing(row.get('diff', 0.0)),
                        replace_missing(row.get('adj_pval', 0.0)),
                    )
                    cursor.execute(sql, values)

# Commit changes and close the connection
db_connection.commit()
cursor.close()
db_connection.close()

print("Data upload complete.")
