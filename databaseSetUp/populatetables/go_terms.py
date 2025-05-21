import pandas as pd
import mysql.connector
import re


# Database configuration
db_config = {
    'host': os.environ.get('MYSQL_HOST'),
    'user': os.environ.get('MYSQL_USER'),
    'database': os.environ.get('MYSQL_DATABASE'),
    'password': os.environ.get('MYSQL_PASSWORD')
}

# Establish a database connection
try:
    db_connection = mysql.connector.connect(**db_config)
    cursor = db_connection.cursor()
    print("Database connection established.")
except mysql.connector.Error as err:
    print(f"Error: {err}")
    exit(1)

# Load TSV file
file_path = 'data/human.tsv'  # Update the file path
data = pd.read_csv(file_path, sep='\t')

def extract_go_terms(go_string):
    """Extract GO terms and IDs from the input string."""
    go_terms = []
    if pd.notna(go_string):
        matches = re.findall(r'([^\[]+)\[GO:(\d+)\]', go_string)
        for term, go_id in matches:
            formatted_term = term.strip().title()
            go_terms.append((formatted_term, go_id))
    return go_terms

# Connect to MySQL
connection = mysql.connector.connect(**db_config)
cursor = connection.cursor()

# Create the table if not exists
create_table_query = '''
CREATE TABLE IF NOT EXISTS go_term (
    go_term_entry_id INT AUTO_INCREMENT,
    go_id VARCHAR(255),
    go_term TEXT,
    accessions TEXT,
    taxonomy_id INT,
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (taxonomy_id) REFERENCES organism(taxonomy_id),
    PRIMARY KEY (go_term_entry_id)
);
'''
cursor.execute(create_table_query)

# Iterate over rows and insert data
for _, row in data.iterrows():
    accession = row['accession']
    taxonomy_id = 9606#row.get('taxonomy_id', None)

    # Extract GO terms from go_f, go_p, go_c columns
    go_columns = ['go_f', 'go_p', 'go_c']
    for col in go_columns:
        go_entries = extract_go_terms(row.get(col, ''))
        for go_term, go_id in go_entries:
            insert_query = '''
            INSERT INTO go_term (go_id, go_term, accessions, taxonomy_id)
            VALUES (%s, %s, %s, %s)
            '''
            try:
                cursor.execute(insert_query, (go_id, go_term, accession, taxonomy_id))
            except Exception as e:
                print(f"Error inserting data: {e}")

# Commit and close
connection.commit()
cursor.close()
connection.close()
