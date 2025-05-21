# dspa-database
 
Code for database upload and database layout.

## 📦 Current Tables in dynaprotdbv2

mysql> SHOW TABLES;
+--------------------------------+
| Tables_in_dynaprotdbv2         |
+--------------------------------+
| differential_abundance         |
| dynaprot_experiment            |
| dynaprot_experiment_comparison |
| go_analysis                    |
| go_term                        |
| organism                       |
| organism_proteome              |
| organism_proteome_entries      |
| protein_scores                 |
+--------------------------------+
9 rows in set (0.00 sec)

## 🚀 Uploading a New Experiment

Use the uploadLipExperiment.sh script to upload an experiment folder to the remote VM, run the upload scripts, and clean up afterward.

This script:

1. Copies the experiment folder to the remote VM.

2. Runs the upload scripts `metadata.py` and `proteinScores.py` located in the src directory.

3. Ingests files such as:

    - params.yaml

    - qc_plots.pdf

    - differential_abundance_<...>.tsv

    - go_term_<...>.tsv

4. Inserts data into the appropriate MySQL tables.

5. Updates table indexes to ensure good database performance.

6. Cleans up the uploaded folder from the VM after processing.

7. Once complete, the experiment becomes visible at:
https://www.dynaprot.org/experiments


## 🛠 Usage

```bash
echo "Usage: ./uploadLipExperiment.sh /path/to/folder vm_username"

./uploadLipExperiment.sh LiP_School9_LiP ekrismer
```

## ⚠️ Important
- The `MYSQL_PASSWORD` is currently set to an empty string in the script for security reasons.

- Do not commit actual passwords or credentials to the repository.

- Instead, export credentials in your shell or use environment files or secrets management tools for production.

