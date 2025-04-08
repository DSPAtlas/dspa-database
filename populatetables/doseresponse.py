import pandas as pd
import mysql.connector

def upload_csv_to_mysql(csv_path):
    try:
        # Read the CSV file
        df = pd.read_csv(csv_path, delimiter='\t')  # Use tab as the delimiter

        # Establish the database connection
        connection = mysql.connector.connect(
            host="localhost",       # Update with your host
            user="your_username",   # Update with your username
            password="your_password", # Update with your password
            database="your_database"  # Update with your database name
        )

        cursor = connection.cursor()

        # Iterate over each row and insert into the table
        for _, row in df.iterrows():
            insert_query = """
            INSERT INTO dose_response_fit (
                dynaprot_experiment, pg_protein_accessions, pep_grouping_key, `rank`, hill_coefficient, 
                min_model, max_model, ec_50, correlation, pval, plot_curve, plot_points, 
                enough_conditions, dose_MNAR, anova_pval, anova_adj_pval, passed_filter, score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """

            data = (
                row['dynaprot_experiment'], row['pg_protein_accessions'], row['pep_grouping_key'], int(row['rank']),
                float(row['hill_coefficient']), float(row['min_model']), float(row['max_model']), 
                float(row['ec_50']), float(row['correlation']), float(row['pval']), 
                str(row['plot_curve']), str(row['plot_points']), 
                bool(row['enough_conditions']), bool(row['dose_MNAR']), 
                float(row['anova_pval']), float(row['anova_adj_pval']), 
                bool(row['passed_filter']), float(row['score'])
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
upload_csv_to_mysql("/path/to/your/csvfile.csv")
