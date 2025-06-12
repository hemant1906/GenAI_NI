import psycopg2
import csv

# Database connection details
DB_HOST = "localhost"  # Use "host.docker.internal" if needed
DB_PORT = "5432"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "mysecretpassword"

# CSV file path
CSV_FILE_PATH_1 =  r'c:\Users\sourav\Downloads\test_data\pgsql_sample_asset_data.csv'
CSV_FILE_PATH_2 =  r'c:\Users\sourav\Downloads\test_data\pgsql_sample_diagram_data.csv'

# Table name
TABLE_NAME_1 = "ASSETS"
TABLE_NAME_2 = "DIAGRAMS"

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Open assets CSV file and insert data
with open(CSV_FILE_PATH_1, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    headers = next(reader)  # Read header row
    columns = ', '.join(headers)  # Convert headers to column names

    for row in reader:
        values = ', '.join(f"'{value}'" for value in row)  # Format values
        query = f"INSERT INTO {TABLE_NAME_1} ({columns}) VALUES ({values});"
        cur.execute(query)

# Open diagrams CSV file and insert data
with open(CSV_FILE_PATH_2, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    headers = next(reader)  # Read header row
    columns = ', '.join(headers)  # Convert headers to column names

    for row in reader:
        values = ', '.join(f"'{value}'" for value in row)  # Format values
        query = f"INSERT INTO {TABLE_NAME_2} ({columns}) VALUES ({values});"
        cur.execute(query)

# Commit changes and close connection
conn.commit()
cur.close()
conn.close()

print("Data successfully ingested!")
