from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
# CORS (REQUIRED)
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# ROOT ENDPOINT (IMPORTANT)
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
# Execute Code
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
# Error Analysis (FINAL FIX)
# -------------------------------
def analyze_error_with_ai(code: str, traceback_str: str) -> List[int]:
    # 🔹 Try AI first
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        prompt = f"""
        Find the exact line number where the error occurred.

        CODE:
        {code}

        TRACEBACK:
        {traceback_str}

        Return ONLY JSON:
        {{"error_lines": [line_numbers]}}
        """

        response = model.generate_content(prompt)
        result = json.loads(response.text.strip())

        if "error_lines" in result and result["error_lines"]:
            return result["error_lines"]

    except:
        pass

    # 🔹 STRONG FALLBACK (IMPORTANT)
    lines = re.findall(r'line (\d+)', traceback_str)

    if lines:
        return [int(lines[-1])]

    return []

# -------------------------------
# API ENDPOINT
# -------------------------------
@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    result = execute_python_code(req.code)

    if result["success"]:
        return {
            "error": [],
            "result": result["output"]
        }

    error_lines = analyze_error_with_ai(req.code, result["output"])

    return {
        "error": error_lines,
        "result": result["output"]
    }