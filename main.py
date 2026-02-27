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
    """Use Gemini AI to find exact error line numbers."""
    
    # Configure Gemini
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = f"""
    Analyze this Python code and its error traceback.
    Identify ONLY the line number(s) where the error occurred.
    
    CODE:
    {code}
    
    TRACEBACK:
    {traceback_str}
    
    Respond with ONLY this JSON format:
    {{"error_lines": [3]}}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
            }
        )
        
        # Parse the JSON response
        import json
        result = json.loads(response.text.strip())
        return result.get("error_lines", [])
        
    except Exception:
        # Fallback: return empty list if AI fails
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
 