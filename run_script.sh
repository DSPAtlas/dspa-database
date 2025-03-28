
# Replace with your MySQL connection details
export MYSQL_USER='host' 
export MYSQL_HOST='localhost'
export MYSQL_DATABASE='dynaprotdbv2'

python3 populatetables/organism.py

python3 populatetables/metadata.py

python3 populatetables/protein_scores.py



