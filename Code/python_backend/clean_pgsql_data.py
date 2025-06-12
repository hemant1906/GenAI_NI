import psycopg2

# Database connection details
DB_HOST = "localhost"  # Use "host.docker.internal" if needed
DB_PORT = "5432"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "mysecretpassword"

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()
query = f"TRUNCATE TABLE ASSETS; TRUNCATE TABLE DIAGRAMS;"
cur.execute(query)

# Commit changes and close connection
conn.commit()
cur.close()
conn.close()

print("Data successfully cleaned up!")
