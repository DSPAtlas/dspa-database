import os
import pandas as pd
import mysql.connector
import math

# MySQL connection details
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    database="dynaprotdb",
)
cursor = db_connection.cursor()

# Function to replace missing values with None
def replace_missing(data, default=None):
    if data is None or data == "" or (isinstance(data, float) and math.isnan(data)):
        return default
    return data

# Path to the directory containing CSV files
csv_directory = "data/go_term/"  # Replace with your folder path

# Iterate through each CSV file in the directory
for file_name in os.listdir(csv_directory):
    if file_name.endswith(".csv"):
        file_path = os.path.join(csv_directory, file_name)
        
        # Load the CSV file into a Pandas DataFrame
        df = pd.read_csv(file_path)
        
        # Replace NaN values with None
        df = df.where(pd.notnull(df), None)
        
        # Iterate through each row in the DataFrame
        for _, row in df.iterrows():
            sql = """
            INSERT INTO go_term (
                go_id, go_term, accessions, taxonomy_id
            ) VALUES (%s, %s, %s, %s)
            """
            values = (
                replace_missing(row['go_id']),
                replace_missing(row['go_term']),
                replace_missing(row['accessions']),
                replace_missing(row['taxonomy_id']),
            )
            try:
                cursor.execute(sql, values)
            except mysql.connector.Error as err:
                print(f"Error: {err}")
                print(f"Failed row: {values}")
                continue

# Commit the changes and close the connection
db_connection.commit()
cursor.close()
db_connection.close()

print("Database population complete.")
