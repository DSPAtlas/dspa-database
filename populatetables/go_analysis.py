import os
import pandas as pd
import mysql.connector

# Replace with your MySQL connection details
table_name = 'go_analysis'

# Create a MySQL connection
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    database="dspasdb",
)
cursor = db_connection.cursor()


# Directory containing the CSV files
csv_directory = "data/go_analysis/new"

# List to store individual DataFrames
dfs = []
columns_to_keep = ['lipexperiment_id', 'term', 'go_id',
                   'pval', 'adj_pval', 'n_detected_proteins', 'n_detected_proteins_in_process',
                   'n_significant_proteins', 'n_significant_proteins_in_process',
                   'enrichment_type']

# Iterate over CSV files in the directory
for filename in os.listdir(csv_directory):
    if filename.endswith(".csv"):
        file_path = os.path.join(csv_directory, filename)

        # Read CSV file into a DataFrame
        df = pd.read_csv(file_path)

        # File format differentialabundance_lipexperimentid.
        experiment_id = filename.split('_')[1].split(".")[0]
        df['lipexperiment_id'] = experiment_id
        df = df[columns_to_keep]
        print(df.head())
        # Append DataFrame to the list
        dfs.append(df)

# Combine all DataFrames into a single DataFrame
combined_df = pd.concat(dfs, ignore_index=True)

# Replace NaN values with None (which becomes NULL in SQL)
combined_df = combined_df.where(pd.notnull(combined_df), None)

# Insert each row into the MySQL table
for index, row in combined_df.iterrows():
    print(row)
    try:
        sql = f"INSERT INTO {table_name} (lipexperiment_id, go_id, term, pval, adj_pval, n_detected_proteins, n_detected_proteins_in_process, n_significant_proteins, n_significant_proteins_in_process, enrichment_type) VALUES (%s, %s,%s, %s, %s, %s, %s, %s, %s, %s)"
        values = (row['lipexperiment_id'], row['go_id'], row['term'], row['pval'], row['adj_pval'], row['n_detected_proteins'], row['n_detected_proteins_in_process'], row['n_significant_proteins'], row['n_significant_proteins_in_process'], row['enrichment_type'])
        cursor.execute(sql, values)
    except:
        print(sql)

# Commit changes and close the connection
db_connection.commit()
cursor.close()
db_connection.close()