import mysql.connector
from mysql.connector import Error
import math

def insert_protein_scores(connection, scores, experiment_id):
    """Insert calculated protein scores into the database."""
    cursor = connection.cursor()
    query = """
    INSERT INTO protein_scores (pg_protein_accessions, protein_description, cumulativeScore, dpx_comparison)
    VALUES (%s, %s, %s, %s)
    """
    values = []
    for accession, score in scores.items():
        # Assuming no description is available, using a placeholder
        description = "Description not available"  # You might want to update this as needed
        values.append((accession, description, score, experiment_id))
    
    try:
        cursor.executemany(query, values)
        connection.commit()
        print(f"Protein scores for experiment {experiment_id} inserted successfully.")
    except Error as err:
        print(f"Failed to insert protein scores: {err}")
    finally:
        cursor.close()


def connect_to_database(host, database, user):
    """Create a database connection."""
    try:
        connection = mysql.connector.connect(
            host=host,
            database=database,
            user=user,
            #password=password
        )
        print("MySQL Database connection successful")
        return connection
    except Error as err:
        print(f"Error: '{err}'")
        return None

def fetch_lip_experiments(connection):
    """Fetch all lip experiments from the database."""
    cursor = connection.cursor(dictionary=True)
    query = "SELECT * FROM dynaprot_experiment_comparison"
    cursor.execute(query)
    experiments = cursor.fetchall()
    cursor.close()
    return experiments

def fetch_differential_abundance_data(connection, lipexperiment_id):
    """Fetch differential abundance data for a given experiment."""
    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT
        pg_protein_accessions,
        pos_start,
        pos_end,
        diff,
        adj_pval
    FROM
        differential_abundance
    WHERE
        dpx_comparison = %s
    """
    cursor.execute(query, (lipexperiment_id,))
    results = cursor.fetchall()
    cursor.close()
    return results

def process_experiment_data(data):
    """Process data for a single experiment to calculate protein scores."""
    qvalue_cutoff = 0.05
    log2FC_cutoff = 0.2
    protein_scores = {}

    for row in data:
        # Check if 'diff' is None and replace it with 0 if it is
        diff_value = row['diff'] if row['diff'] is not None else 0
        log2FC = 0 if not math.isfinite(diff_value) else diff_value
        qvalue = row['adj_pval']

        # Check if 'adj_pval' is None and continue to next iteration if it is
        if qvalue is None:
            continue
        
        # Calculate score only if both qvalue and log2FC have valid numerical values
        if qvalue is not None and log2FC is not None:
            score = -math.log10(qvalue + 1e-10) + abs(log2FC)
            protein_accession = row['pg_protein_accessions']
            if protein_accession not in protein_scores:
                protein_scores[protein_accession] = 0
            
            if qvalue < qvalue_cutoff and abs(log2FC) > log2FC_cutoff:
                protein_scores[protein_accession] += score

    return protein_scores


def main():
    # Database credentials
    host = 'localhost'
    database = 'dynaprotdbv2'
    user = 'root'
   # password = 'your_password'
    
    # Connect to the database
    connection = connect_to_database(host, database, user)
    if connection:
        # Fetch all experiments
        experiments = fetch_lip_experiments(connection)
        
        # Process each experiment
        for experiment in experiments:
            print(f"Processing experiment {experiment['dpx_comparison']}")
            data = fetch_differential_abundance_data(connection, experiment['dpx_comparison'])
            scores = process_experiment_data(data)
            print(f"Scores for {experiment['dpx_comparison']}: {scores}")
            insert_protein_scores(connection, scores, experiment['dpx_comparison'])

        # Close the database connection
        connection.close()
    else:
        print("Failed to connect to the database")

if __name__ == "__main__":
    main()
