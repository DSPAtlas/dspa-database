import pandas as pd
import mysql.connector
import numpy as np
import math
import re


def safe_float(value):
    """Safely convert a value to float and handle out-of-range errors."""
    try:
        if value is None or pd.isna(value):
            return None  # Return None directly if the value is None or NaN
        
        float_value = float(value)

        # Clamp the value to MySQL FLOAT range
        max_float = 3.402823466E+38
        min_float = -3.402823466E+38

        # Check if the value is within range
        if not math.isfinite(float_value):
            return 0.0  # Return 0.0 for non-finite values
        elif float_value > max_float:
            return max_float  # Cap at max float
        elif float_value < min_float:
            return min_float  # Cap at min float
        else:
            return float_value
    except (ValueError, OverflowError, TypeError):
        # Return 0.0 as a fallback
        return 0.0


def upload_csv_to_mysql(csv_path):
    try:
        # Read the CSV file
        df = pd.read_csv(csv_path, delimiter=',') 
        df = df.replace({np.nan: None})

        # Establish the database connection
        connection = mysql.connector.connect(
          host="localhost",
            user="root",
            database="dynaprotdbv2",
        )

        cursor = connection.cursor()

        # Iterate over each row and insert into the table
        for _, row in df.iterrows():
            insert_query = """
            INSERT INTO dose_response_fit (
                dynaprot_experiment, pg_protein_accessions, pep_grouping_key, `rank`, hill_coefficient, 
                min_model, max_model, ec_50, correlation, pval,  
                enough_conditions, dose_MNAR, anova_pval, anova_adj_pval, passed_filter, score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
 
            data = (
                'DPX000012', row['pg_protein_accessions'], row['eg_modified_peptide'], 
                int(row['rank']) if pd.notna(row['rank']) else None,
                safe_float(row['hill_coefficient']),
                safe_float(row['min_model']),
                safe_float(row['max_model']),
                safe_float(row['ec_50']),
                safe_float(row['correlation']),
                safe_float(row['pval']),
                bool(row['enough_conditions']) if pd.notna(row['enough_conditions']) else None,
                bool(row['dose_MNAR']) if pd.notna(row['dose_MNAR']) else None,
                safe_float(row['anova_pval']),
                safe_float(row['anova_adj_pval']),
                bool(row['passed_filter']) if pd.notna(row['passed_filter']) else None,
                safe_float(row['score'])
            )


            cursor.execute(insert_query, data)

        connection.commit()
        print("Data uploaded successfully!")

    except mysql.connector.Error as error:
        print(f"Error: {error}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

# Call the function with the path to your CSV file
upload_csv_to_mysql("/Users/ekrismer/Documents/lipatlasdata/PXD015446_Ilaria_Rapamycin/lipquant_results.csv")
