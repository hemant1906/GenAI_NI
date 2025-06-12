from fastapi import FastAPI, HTTPException, Query
import psycopg2
import os

# Database connection details
DB_HOST = "localhost"  # Use "host.docker.internal" if needed
DB_PORT = "5432"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "mysecretpassword"

# Initialize FastAPI
app = FastAPI()

# Function to fetch asset details
def get_asset_details(asset_id):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT * FROM assets WHERE asset_id = %s;"
    cur.execute(query, (asset_id,))
    results = cur.fetchall()

    cur.close()
    conn.close()

    if results:
        columns = ["asset_id", "asset_name", "asset_description", "asset_domain", "asset_capability", "asset_diagram_id"]  # Adjust based on your table schema
        return [dict(zip(columns, row)) for row in results]  # Convert each row to a dictionary
    else:
        return None

# Function to list all assets matching partially the asset name
def get_assets_by_name_pattern(asset_name_pattern):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT asset_id, asset_name FROM assets WHERE asset_name ILIKE %s;"
    print(query)
    cur.execute(query, (asset_name_pattern,))  # Passing pattern as parameter
    results = cur.fetchall()
    print(results)

    cur.close()
    conn.close()

    if results:
        columns = ["asset_id", "asset_name"]
        return [dict(zip(columns, row)) for row in results]  # Convert each row to a dictionary
    else:
        return None

# Function to fetch diagram details
def get_diagram_details(diagram_id):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT * FROM diagrams WHERE diagram_id = %s;"
    cur.execute(query, (diagram_id,))
    results = cur.fetchall()

    cur.close()
    conn.close()

    if results:
        columns = ["diagram_id", "diagram_name", "diagram_mermaid_code"]
        return [dict(zip(columns, row)) for row in results]  # Convert each row to a dictionary
    else:
        return None

# Function to fetch mermaid code from asset id
def get_mermaid_code_for_asset(asset_id):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT diagram_mermaid_code FROM diagrams WHERE diagram_id = (SELECT asset_diagram_id FROM assets WHERE asset_id = %s);"
    cur.execute(query, (asset_id,))
    result = cur.fetchone() # Only one mermaid code expected

    cur.close()
    conn.close()

    if result:
        columns = ["diagram_mermaid_code"]
        return [dict(zip(columns, result))]
    else:
        return None

# Function to fetch all assets of a particular domain and capability
def get_assets_for_dom_cap(asset_domain, asset_capability):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT asset_id, asset_diagram_id FROM assets WHERE asset_domain = %s AND asset_capability = %s;"
    cur.execute(query, (asset_domain, asset_capability))
    results = cur.fetchall()

    cur.close()
    conn.close()

    if results:
        columns = ["asset_id", "asset_diagram_id"]
        return [dict(zip(columns, row)) for row in results]  # Convert each row to a dictionary
    else:
        return None

# API Endpoint to fetch asset details
@app.get("/asset/{asset_id}")
async def fetch_asset(asset_id: str):
    asset = get_asset_details(asset_id)
    if asset:
        return asset
    else:
        raise HTTPException(status_code=404, detail="Asset not found")

# API Endpoint to fetch diagram details
@app.get("/diagram/{diagram_id}")
async def fetch_asset(diagram_id: str):
    diagram = get_diagram_details(diagram_id)
    if diagram:
        return diagram
    else:
        raise HTTPException(status_code=404, detail="Diagram not found")

# API Endpoint to fetch assets by domain and capability
@app.get("/assets/")
async def fetch_assets(asset_domain: str = Query(...), asset_capability: str = Query(...)):
    assets = get_assets_for_dom_cap(asset_domain, asset_capability)
    if assets:
        return assets
    else:
        raise HTTPException(status_code=404, detail="No matching assets found")

# API Endpoint to list all assets matching partially the asset name
@app.get("/assets/search/")
async def search_assets(asset_name: str = Query(...)):
    name_pattern = asset_name + "%"  # Append '%' for partial matching
    assets = get_assets_by_name_pattern(name_pattern)
    if assets:
        return assets
    else:
        raise HTTPException(status_code=404, detail="No matching assets found")

# API Endpoint to get mermaid code from asset id
@app.get("/mermaid/{asset_id}")
async def fetch_mermaid(asset_id: str):
    mermaid = get_mermaid_code_for_asset(asset_id)
    if mermaid:
        return mermaid
    else:
        raise HTTPException(status_code=404, detail="No matching assets found")
