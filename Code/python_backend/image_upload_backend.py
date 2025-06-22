from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import uuid
import psycopg2
import io
from PIL import Image
import google.generativeai as genai
from chromadb_store import store_diagram_summary  # <- from your external file

# Load API Key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# DB connection
conn = psycopg2.connect(
    dbname="postgres", user="postgres", password="mysecretpassword", host="localhost", port="5432"
)
cur = conn.cursor()

# FastAPI App
app = FastAPI()

# CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

def clean_mermaid_code(raw: str) -> str:
    lines = raw.strip().splitlines()
    if lines[0].strip().startswith("```"):  # First line is ```mermaid or similar
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):  # Last line is ```
        lines = lines[:-1]
    return "\n".join(lines).strip()

@app.post("/upload/")
async def upload_image(image: UploadFile, diagram_name: str = Form(...), asset_id: str = Form(...)):
    try:

        # 1. Read and convert image
        image_bytes = await image.read()
        image_pil = Image.open(io.BytesIO(image_bytes))

        # 2. Prepare Gemini model & prompt
        model = genai.GenerativeModel('gemini-2.5-pro')
        prompt = "Convert this image into a valid Mermaid diagram. Only return the Mermaid code, starting directly with `graph TD`. Do NOT include the word `mermaid` or any explanation. Return only the diagram code block with correct formatting and indentation."

        # 3. Generate Mermaid code
        response = model.generate_content([prompt, image_pil])
        raw_mermaid_code = response.text.strip()

        # 4. Clean it
        mermaid_code = clean_mermaid_code(raw_mermaid_code)

        # 5. Store Mermaid code in DIAGRAMS table
        diagram_id = str(uuid.uuid4())

        # 6. Store diagram code in PGSQL
        cur.execute(
            "INSERT INTO diagrams (diagram_id, diagram_name, diagram_mermaid_code) VALUES (%s, %s, %s)",
            (diagram_id, diagram_name, mermaid_code)
        )

        # 7. Associate or insert into ASSETS table
        cur.execute("SELECT * FROM assets WHERE asset_id = %s", (asset_id,))
        if cur.fetchone():
            cur.execute("UPDATE assets SET asset_diagram_id = %s WHERE asset_id = %s",
                        (diagram_id, asset_id))
        else:
            cur.execute("INSERT INTO assets (asset_id, asset_diagram_id) VALUES (%s, %s)",
                        (asset_id, diagram_id))

        # 8. Get Summary & Description
        summary_prompt = f"Summarize this diagram in 50 words:\n{mermaid_code}"
        summary_resp = model.generate_content(summary_prompt)
        summary = summary_resp.text.strip()

        desc_prompt = f"Describe this diagram in detail (~200 words):\n{mermaid_code}"
        desc_resp = model.generate_content(desc_prompt)
        description = desc_resp.text.strip()

        # 9. Store summary & description in ChromaDB
        store_diagram_summary(
            diagram_id=diagram_id,
            diagram_name=diagram_name,
            asset_id=asset_id,
            summary=summary,
            description=description
        )

        conn.commit()

        return JSONResponse({
            "status": "success",
            "diagram_id": diagram_id,
            "mermaid_code": mermaid_code,
            "summary": summary,
            "description": description
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
