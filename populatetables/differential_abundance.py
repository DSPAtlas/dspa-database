import os
import pandas as pd
import mysql.connector

# Replace with your MySQL connection details

mysql_user = os.environ.get('MYSQL_USER')
mysql_password = os.environ.get('MYSQL_PASSWORD')
mysql_host = os.environ.get('MYSQL_HOST')
mysql_database = os.environ.get('MYSQL_DATABASE')
table_name = 'differential_abundance'

# Create a MySQL connection
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    #password=mysql_password,
    database="dynaprotdb",
)
cursor = db_connection.cursor()


# Directory containing the CSV files
csv_directory = "data/differential_abundance/"

# List to store individual DataFrames
dfs = []
columns_to_keep = ['lipexperiment_id', 'pg_protein_accessions', 'pep_grouping_key',
                   'pos_start', 'pos_end', 'diff', 'adj_pval']

# Iterate over CSV files in the directory
for filename in os.listdir(csv_directory):
    if filename.endswith(".csv"):
        file_path = os.path.join(csv_directory, filename)

        # Read CSV file into a DataFrame
        df = pd.read_csv(file_path, quotechar='"')

        # File format differentialabundance_lipexperimentid.
        experiment_id = filename.split('_')[1].split(".")[0]
        df['lipexperiment_id'] = experiment_id
        print("lipexperimen", experiment_id)
        df = df.rename(columns={'start': 'pos_start', 'end': 'pos_end', "pep_stripped_sequence": "pep_grouping_key"})
        df = df[columns_to_keep]
        print(df.head())
        # Append DataFrame to the list
        dfs.append(df)

# Combine all DataFrames into a single DataFrame
combined_df = pd.concat(dfs, ignore_index=True)

# Replace NaN values with None (which becomes NULL in SQL)
combined_df = combined_df.where(pd.notnull(combined_df), None)

# Set 'lip_experiment_id' and 'pg_protein_accessions' as the primary key
#combined_df.set_index(['lipexperiment_id', 'pg_protein_accessions', 'pep_grouping_key'], inplace=True)
cursor.execute("SELECT lipexperiment_id FROM lip_experiments")
existing_ids = {row[0] for row in cursor.fetchall()}

# Insert each row into the MySQL table
for index, row in combined_df.iterrows():
    if row['lipexperiment_id'] not in existing_ids:
        print(f"Skipping row with missing lipexperiment_id: {row['lipexperiment_id']}")
        continue

    try:
        sql = f"INSERT INTO {table_name} (lipexperiment_id, pg_protein_accessions, pep_grouping_key, pos_start, pos_end, diff, adj_pval) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        values = (row['lipexperiment_id'], row['pg_protein_accessions'], row['pep_grouping_key'], row['pos_start'], row['pos_end'], row['diff'], row['adj_pval'])
        cursor.execute(sql, values)
    except Exception as e:
        print("Error executing SQL:", sql)
        print("Values:", values)
        print("Error message:", e)

# Commit changes and close the connection
db_connection.commit()
cursor.close()
db_connection.close()