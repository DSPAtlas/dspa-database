# Function to update or insert records into lip_experiments table¨
import os
import pandas as pd
import mysql.connector
import math

def replace_missing(data, default=None):
    if data is None or data == "" or (isinstance(data, float) and math.isnan(data)):
        return default
    return data

def upsert_lip_experiment(cursor, data, pdf_data):
    select_sql = "SELECT lipexperiment_id FROM lip_experiments WHERE lipexperiment_id = %s"
    cursor.execute(select_sql, (data["lipexperiment_id"],))
    result = cursor.fetchone()
    
    if result:  # Record exists, perform an update
        update_sql = """
        UPDATE lip_experiments
        SET 
            perturbation = %s,
            `condition` = %s,
            taxonomy_id = %s,
            strain = %s,
            instrument = %s,
            number_of_lip_files = %s,
            numer_of_tr_files = %s,
            experiment = %s,
            approach = %s,
            reference_for_protocol = %s,
            data_analysis = %s,
            publication = %s,
            doi = %s,
            search_settings = %s,
            fasta = %s,
            data_re_analysis_settings = %s,
            path_to_raw_files = %s,
            digestion_protocol = %s,
            e_s_ratio = %s,
            pk_digestion_time_in_sec = %s,
            protease = %s,
            author = %s,
            input_file = %s,
            qc_pdf_file = %s
        WHERE 
            lipexperiment_id = %s
        """
        values = (
            replace_missing(data["perturbation"]),
            replace_missing(data["condition"]),
            int(data.get("taxonomy_id", 0)),
            replace_missing(data["strain"]),
            replace_missing(data["instrument"]),
            int(data.get("number_of_lip_files", 0)),
            int(data.get("numer_of_tr_files", 0)),
            replace_missing(data["experiment"]),
            replace_missing(data["approach"]),
            replace_missing(data["reference_for_protocol"]),
            replace_missing(data["data_analysis"]),
            replace_missing(data["publication"]),
            replace_missing(data["doi"]),
            replace_missing(data["search_settings"]),
            replace_missing(data["fasta"]),
            replace_missing(data["data_re_analysis_settings"]),
            replace_missing(data["path_to_raw_files"]),
            replace_missing(data["digestion_protocol"]),
            replace_missing(data["e_s_ratio"]),
            replace_missing(data["pk_digestion_time_in_sec"]),
            replace_missing(data["protease"]),
            replace_missing(data["author"]),
            replace_missing(data["input_file"]),
            pdf_data,
            data["lipexperiment_id"],
        )
        cursor.execute(update_sql, values)
    else:  # Record does not exist, perform an insert
        insert_sql = """
        INSERT INTO lip_experiments (
            lipexperiment_id, perturbation, `condition`, taxonomy_id, strain,
            instrument, number_of_lip_files, numer_of_tr_files, experiment,
            approach, reference_for_protocol, data_analysis, publication, doi,
            search_settings, fasta, data_re_analysis_settings, path_to_raw_files,
            digestion_protocol, e_s_ratio, pk_digestion_time_in_sec, protease, author,
            input_file, qc_pdf_file
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            replace_missing(data["lipexperiment_id"]),
            replace_missing(data["perturbation"]),
            replace_missing(data["condition"]),
            int(data.get("taxonomy_id", 0)),
            replace_missing(data["strain"]),
            replace_missing(data["instrument"]),
            int(data.get("number_of_lip_files", 0)),
            int(data.get("numer_of_tr_files", 0)),
            replace_missing(data["experiment"]),
            replace_missing(data["approach"]),
            replace_missing(data["reference_for_protocol"]),
            replace_missing(data["data_analysis"]),
            replace_missing(data["publication"]),
            replace_missing(data["doi"]),
            replace_missing(data["search_settings"]),
            replace_missing(data["fasta"]),
            replace_missing(data["data_re_analysis_settings"]),
            replace_missing(data["path_to_raw_files"]),
            replace_missing(data["digestion_protocol"]),
            replace_missing(data["e_s_ratio"]),
            replace_missing(data["pk_digestion_time_in_sec"]),
            replace_missing(data["protease"]),
            replace_missing(data["author"]),
            replace_missing(data["input_file"]),
            pdf_data,
        )
        cursor.execute(insert_sql, values)

base_directory = "data/"
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    database="dynaprotdb",
)
cursor = db_connection.cursor()

# Iterate through experiment folders and apply upsert logic
for folder in os.listdir(base_directory):
    folder_path = os.path.join(base_directory, folder)
    if not os.path.isdir(folder_path):
        continue

    # Parse params file
    params_file = os.path.join(folder_path, "params.yaml")
    pdf_path = os.path.join(folder_path, "qc_plots.pdf")
    pdf_data = None
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()

    if os.path.exists(params_file):
        with open(params_file, "r") as file:
            params_data = {}
            for line in file:
                key, value = line.strip().split(": ", 1)
                params_data[key] = value.strip('"')

        experiment_ids = eval(params_data.get("experiment_id", "[]"))
        for experiment_id in experiment_ids:
            data = {**params_data, "lipexperiment_id": experiment_id}
            upsert_lip_experiment(cursor, data, pdf_data)

# Commit changes and close the connection
db_connection.commit()
cursor.close()
db_connection.close()

print("Data update and upload complete.")

