from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import sys
from io import StringIO
import traceback
import os

import google.generativeai as genai

app = FastAPI()

# -------------------------------
# Enable CORS (IMPORTANT)
# -------------------------------
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Request Model
# -------------------------------
class CodeRequest(BaseModel):
    code: str

# -------------------------------
# Execute Code (TOOL FUNCTION)
# -------------------------------
def execute_python_code(code: str):
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}

    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}

    finally:
        sys.stdout = old_stdout

# -------------------------------
# AI Error Analysis
# -------------------------------
def analyze_error_with_ai(code: str, tb: str):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
Find the line number where the error occurred.

CODE:
{code}

TRACEBACK:
{tb}

Return JSON like:
{{"error_lines": [line_numbers]}}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")

    response = model.generate_content(prompt)

    import json
    try:
        data = json.loads(response.text)
        return data.get("error_lines", [])
    except:
        return []

# -------------------------------
# API ENDPOINT
# -------------------------------
@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    result = execute_python_code(req.code)

    # ✅ No error
    if result["success"]:
        return {
            "error": [],
            "result": result["output"]
        }

    # ❌ Error → call AI
    lines = analyze_error_with_ai(req.code, result["output"])

    return {
        "error": lines,
        "result": result["output"]
    }