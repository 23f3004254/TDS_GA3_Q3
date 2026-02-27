from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sys
from io import StringIO
import traceback
import os
import google.generativeai as genai
from pydantic import BaseModel as PydanticBaseModel

# Initialize FastAPI app
app = FastAPI()

# Enable CORS (required for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class CodeRequest(BaseModel):
    code: str

class ErrorAnalysis(PydanticBaseModel):
    error_lines: List[int]

class InterpreterResponse(BaseModel):
    error: List[int]
    result: str

# Step 1: The Code Runner Tool (exactly as provided)
def execute_python_code(code: str) -> dict:
    """Execute Python code and return exact output."""
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

# Step 2: AI Error Detective (fixed version)
def analyze_error_with_ai(code: str, traceback_str: str) -> List[int]:
    import re
    import json

    # 🔹 Step 1: Try AI
    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
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
        pass  # fallback below

    # 🔹 Step 2: FALLBACK (CRITICAL FIX ✅)
    match = re.search(r'line (\d+)', traceback_str)
    if match:
        return [int(match.group(1))]

    return []
# Step 3: The Main API Endpoint
@app.post("/code-interpreter", response_model=InterpreterResponse)
async def code_interpreter(request: CodeRequest):
    """Main endpoint: run code + AI error analysis."""
    
    # 1. Run the code
    execution_result = execute_python_code(request.code)
    
    # 2. Check if successful
    if execution_result["success"]:
        return InterpreterResponse(
            error=[],
            result=execution_result["output"]
        )
    
    # 3. Error occurred → call AI detective
    error_lines = analyze_error_with_ai(
        code=request.code,
        traceback_str=execution_result["output"]
    )
    
    return InterpreterResponse(
        error=error_lines,
        result=execution_result["output"]
    )

# Health check
@app.get("/")
def root():
    return {"message": "Code Interpreter API is running!"}
 