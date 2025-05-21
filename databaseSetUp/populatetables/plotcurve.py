import pandas as pd
import mysql.connector
import numpy as np
import math


def safe_float(value):
    """Safely convert a value to float and handle out-of-range errors."""
    try:
        if value is None or pd.isna(value):
            return None
        float_value = float(value)
        max_float = 3.402823466E+38
        min_float = -3.402823466E+38
        if not math.isfinite(float_value):
            return 0.0
        elif float_value > max_float:
            return max_float
        elif float_value < min_float:
            return min_float
        else:
            return float_value
    except (ValueError, OverflowError, TypeError):
        return 0.0


def upload_csv_to_mysql(csv_path, table_name, columns, dynaprot_experiment):
    try:
        df = pd.read_csv(csv_path, delimiter=',')
        df = df.replace({np.nan: None})

        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            database="dynaprotdbv2",
        )
        cursor = connection.cursor()

        for _, row in df.iterrows():
            placeholders = ', '.join(['%s'] * len(columns))
            insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders});"
            data = (dynaprot_experiment,) + tuple(safe_float(row[col]) if isinstance(row[col], float) else row[col] for col in columns[1:])
            cursor.execute(insert_query, data)

        connection.commit()
        print(f"Data uploaded successfully to {table_name}!")
    except mysql.connector.Error as error:
        print(f"MySQL Error: {error}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")


# Upload dose_response_plot_curve.csv
upload_csv_to_mysql(
    "/Users/ekrismer/Documents/lipatlasdata/PXD015446_Ilaria_Rapamycin/lipquant_plot_curve.csv",
    "dose_response_plot_curve",
    ["dynaprot_experiment", "pep_grouping_key", "dose", "prediction", "lower", "upper"],
    "DPX000012"
)

# Upload dose_response_plot_points.csv
upload_csv_to_mysql(
    "/Users/ekrismer/Documents/lipatlasdata/PXD015446_Ilaria_Rapamycin/lipquant_plot_points.csv",
    "dose_response_plot_points",
    ["dynaprot_experiment", "pep_grouping_key", "normalised_intensity_log2", "dose"],
    "DPX000012"
)
