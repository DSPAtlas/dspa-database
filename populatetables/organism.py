import os
import gzip
import json
from Bio import SeqIO
import mysql.connector
import re
# Connect to MySQL database

db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    database="dynaprotdbv2",)

cursor = db_connection.cursor()

# Directory containing the gzipped fasta files
fasta_directory = "data/fasta/"

# Function to serialize fasta file to JSON
def serialize_fasta_to_json(fasta_file):
    fasta_records = list(SeqIO.parse(fasta_file, "fasta"))
    serialized_data = {}
    for record in fasta_records:
        protein_id = record.id.split("|")[1]
        serialized_data[protein_id] = str(record.seq)
    return json.dumps(serialized_data)

for filename in os.listdir(fasta_directory):
    if filename.endswith(".fasta.gz"):
        # Extract taxonomy_id and proteome_id from the filename
        proteome_id, taxonomy_id = filename.split("_")[:2]
        taxonomy_id = str(taxonomy_id.split(".")[0])

        with gzip.open(os.path.join(fasta_directory, filename), "rt") as handle:
            fasta = list(SeqIO.parse(handle, "fasta"))
                    
        for rec in fasta:
            seq_id = rec.id
            seq = str(rec.seq) 
            protein_name = rec.id.split("|")[1]
            description_full = rec.description
            # Extract everything after first space and before 'OS='
            match = re.search(r'^[^ ]+ (.+?) OS=', description_full)
            if match:
                protein_description = match.group(1)
            else:
                # fallback if 'OS=' not present
                protein_description = description_full.split(" ", 1)[-1]
            protein_description = protein_description[:255]  

            # Insert data into 'organism_proteome' table
            cursor.execute("""
            INSERT INTO organism_proteome_entries (proteome_id, taxonomy_id, seq_id, seq, protein_name, protein_description)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (proteome_id, taxonomy_id, seq_id, seq, protein_name, protein_description))

# Commit changes and close connections
db_connection.commit()
cursor.close()
db_connection.close()