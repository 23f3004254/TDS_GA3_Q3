from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import sys
from io import StringIO
import traceback
import os
import json
import re

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
# ROOT ENDPOINT (VERY IMPORTANT)
# -------------------------------
@app.get("/")
def home():
    return {"message": "API is running"}

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
Analyze the Python code and traceback.

Return ONLY JSON in this format:
{{"error_lines": [line_numbers]}}

CODE:
{code}

TRACEBACK:
{tb}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")

    response = model.generate_content(prompt)

    try:
        # Try proper JSON parsing
        data = json.loads(response.text)
        return data.get("error_lines", [])
    except:
        # Fallback: extract numbers manually
        numbers = re.findall(r'\d+', response.text)
        return [int(n) for n in numbers]

# -------------------------------
# API ENDPOINT
# -------------------------------
@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    result = execute_python_code(req.code)

    # ✅ If no error
    if result["success"]:
        return {
            "error": [],
            "result": result["output"]
        }

    # ❌ If error → call AI
    lines = analyze_error_with_ai(req.code, result["output"])

    return {
        "error": lines,
        "result": result["output"]
    }