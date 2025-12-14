from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import json
import os
from typing import Optional
from pathlib import Path
import uuid

app = FastAPI()

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b-instruct-q4_K_M")
RESUMES_DIR = Path("./data/resumes")
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

class SkillAnalysisRequest(BaseModel):
    resume_text: Optional[str] = None
    resume_id: Optional[str] = None
    job_description: Optional[str] = None

class SkillGapAnalysisRequest(BaseModel):
    resume_text: Optional[str] = None
    resume_id: Optional[str] = None
    target_role: str

class WeeklyLearningTaskRequest(BaseModel):
    resume_text: Optional[str] = None
    resume_id: Optional[str] = None
    missing_skills: Optional[list] = None

@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            if response.status_code == 200:
                return {"status": "healthy", "ollama": "connected"}
            else:
                return {"status": "degraded", "ollama": "unavailable"}
    except Exception:
        return {"status": "degraded", "ollama": "unavailable"}

@app.post("/upload_resume")
async def upload_resume(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    try:
        if file:
            content = await file.read()
            resume_text = content.decode('utf-8')
            filename = file.filename or "resume.txt"
        elif text:
            resume_text = text
            filename = "resume.txt"
        else:
            raise HTTPException(status_code=400, detail="Either file or text must be provided")
        
        resume_id = str(uuid.uuid4())
        file_path = RESUMES_DIR / f"{resume_id}.txt"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(resume_text)
        
        return {
            "resume_id": resume_id,
            "filename": filename,
            "size": len(resume_text),
            "message": "Resume uploaded successfully",
            "path": str(file_path)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing resume: {str(e)}")

@app.post("/analyze_skills")
async def analyze_skills(request: SkillAnalysisRequest):
    resume_text = None
    
    if request.resume_id:
        file_path = RESUMES_DIR / f"{request.resume_id}.txt"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
    elif request.resume_text:
        resume_text = request.resume_text
    else:
        raise HTTPException(status_code=400, detail="Either resume_text or resume_id is required")
    
    prompt = f"""Analyze this resume and extract information. Return ONLY valid JSON, no other text.

Resume:
{resume_text}

Return JSON in this exact format:
{{
  "skills": ["skill1", "skill2", ...],
  "years_experience": "X years" or null,
  "role_suggestions": ["role1", "role2", ...]
}}"""

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 800
                    }
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text if hasattr(response, 'text') else "Ollama service error"
                raise HTTPException(status_code=500, detail=f"Ollama service error: {error_detail}")
            
            result = response.json()
            analysis_text = result.get("response", "").strip()
            
            try:
                analysis_text = analysis_text.strip()
                
                if analysis_text.startswith("```json"):
                    analysis_text = analysis_text[7:]
                if analysis_text.startswith("```"):
                    analysis_text = analysis_text[3:]
                if analysis_text.endswith("```"):
                    analysis_text = analysis_text[:-3]
                analysis_text = analysis_text.strip()
                
                first_brace = analysis_text.find('{')
                last_brace = analysis_text.rfind('}')
                
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = analysis_text[first_brace:last_brace + 1]
                else:
                    json_str = analysis_text
                
                analysis_json = json.loads(json_str)
                
                if not isinstance(analysis_json, dict):
                    raise ValueError("Response is not a JSON object")
                
                result_data = {
                    "skills": analysis_json.get("skills", []),
                    "years_experience": analysis_json.get("years_experience"),
                    "role_suggestions": analysis_json.get("role_suggestions", [])
                }
                
                return result_data
            except json.JSONDecodeError as e:
                return {
                    "skills": [],
                    "years_experience": None,
                    "role_suggestions": [],
                    "error": "Failed to parse LLM response as JSON",
                    "raw_response": analysis_text[:500]
                }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout. Ollama may be slow or unresponsive.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama service. Ensure Ollama is running at http://localhost:11434")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Ollama connection error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def _extract_skills_from_resume(resume_text: str) -> dict:
    prompt = f"""Analyze this resume and extract skills. Return ONLY valid JSON.

Resume:
{resume_text}

Return JSON:
{{
  "skills": ["skill1", "skill2", ...]
}}"""

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 600
                    }
                }
            )
            
            if response.status_code != 200:
                return {"skills": []}
            
            result = response.json()
            analysis_text = result.get("response", "").strip()
            
            try:
                first_brace = analysis_text.find('{')
                last_brace = analysis_text.rfind('}')
                
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = analysis_text[first_brace:last_brace + 1]
                else:
                    json_str = analysis_text
                
                analysis_json = json.loads(json_str)
                return {"skills": analysis_json.get("skills", [])}
            except Exception:
                return {"skills": []}
    except Exception:
        return {"skills": []}

@app.post("/skill_gap_analysis")
async def skill_gap_analysis(request: SkillGapAnalysisRequest):
    resume_text = None
    
    if request.resume_id:
        file_path = RESUMES_DIR / f"{request.resume_id}.txt"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
    elif request.resume_text:
        resume_text = request.resume_text
    else:
        raise HTTPException(status_code=400, detail="Either resume_text or resume_id is required")
    
    extracted_skills_data = await _extract_skills_from_resume(resume_text)
    extracted_skills = extracted_skills_data.get("skills", [])
    
    prompt = f"""Compare the candidate's skills against the target role requirements and identify missing skills.

Candidate's Skills: {', '.join(extracted_skills) if extracted_skills else 'None listed'}
Target Role: {request.target_role}

Return ONLY valid JSON:
{{
  "missing_skills": ["skill1", "skill2", ...]
}}"""

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 600
                    }
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ollama service error")
            
            result = response.json()
            analysis_text = result.get("response", "").strip()
            
            missing_skills = []
            try:
                first_brace = analysis_text.find('{')
                last_brace = analysis_text.rfind('}')
                
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = analysis_text[first_brace:last_brace + 1]
                else:
                    json_str = analysis_text
                
                gap_json = json.loads(json_str)
                missing_skills = gap_json.get("missing_skills", [])
            except Exception:
                missing_skills = []
            
            weekly_tasks = []
            if missing_skills:
                task_prompt = f"""Generate 5-7 practical weekly learning tasks for each missing skill. Return ONLY valid JSON.

Missing Skills: {', '.join(missing_skills)}

Return JSON:
{{
  "weekly_tasks": [
    {{"skill": "skill1", "tasks": ["task1", "task2", "task3", "task4", "task5", "task6", "task7"]}},
    {{"skill": "skill2", "tasks": ["task1", "task2", "task3", "task4", "task5"]}}
  ]
}}"""

                task_response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": task_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.5,
                            "num_predict": 1500
                        }
                    }
                )
                
                if task_response.status_code == 200:
                    task_result = task_response.json()
                    task_text = task_result.get("response", "").strip()
                    
                    try:
                        first_brace = task_text.find('{')
                        last_brace = task_text.rfind('}')
                        
                        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                            json_str = task_text[first_brace:last_brace + 1]
                        else:
                            json_str = task_text
                        
                        task_json = json.loads(json_str)
                        weekly_tasks = task_json.get("weekly_tasks", [])
                    except Exception:
                        pass
                
                if not weekly_tasks:
                    for skill in missing_skills:
                        weekly_tasks.append({
                            "skill": skill,
                            "tasks": [
                                f"Study {skill} fundamentals and core concepts",
                                f"Complete online {skill} tutorial or course",
                                f"Practice {skill} with hands-on exercises",
                                f"Build a small project using {skill}",
                                f"Read {skill} documentation and best practices",
                                f"Join {skill} community and participate in discussions",
                                f"Create a portfolio piece showcasing {skill}"
                            ][:7]
                        })
            
            return {
                "extracted_skills": extracted_skills,
                "missing_skills": missing_skills,
                "weekly_tasks": weekly_tasks
            }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout. Ollama may be slow or unresponsive.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama service. Ensure Ollama is running at http://localhost:11434")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Ollama connection error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/weekly_learning_task_generator")
async def weekly_learning_task_generator(request: WeeklyLearningTaskRequest):
    missing_skills = request.missing_skills or []
    extracted_skills = []
    
    if not missing_skills:
        resume_text = None
        
        if request.resume_id:
            file_path = RESUMES_DIR / f"{request.resume_id}.txt"
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Resume not found")
            with open(file_path, 'r', encoding='utf-8') as f:
                resume_text = f.read()
        elif request.resume_text:
            resume_text = request.resume_text
        else:
            raise HTTPException(status_code=400, detail="Either resume_text, resume_id, or missing_skills must be provided")
        
        extracted_skills_data = await _extract_skills_from_resume(resume_text)
        extracted_skills = extracted_skills_data.get("skills", [])
    
    if not missing_skills:
        return {
            "extracted_skills": extracted_skills,
            "missing_skills": [],
            "weekly_tasks": []
        }
    
    prompt = f"""Generate 5-7 practical weekly learning tasks for each missing skill. Return ONLY valid JSON.

Missing Skills: {', '.join(missing_skills)}

Return JSON:
{{
  "weekly_tasks": [
    {{"skill": "skill1", "tasks": ["task1", "task2", "task3", "task4", "task5", "task6", "task7"]}},
    {{"skill": "skill2", "tasks": ["task1", "task2", "task3", "task4", "task5"]}}
  ]
}}"""

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "num_predict": 1500
                    }
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ollama service error")
            
            result = response.json()
            analysis_text = result.get("response", "").strip()
            
            weekly_tasks = []
            try:
                first_brace = analysis_text.find('{')
                last_brace = analysis_text.rfind('}')
                
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = analysis_text[first_brace:last_brace + 1]
                else:
                    json_str = analysis_text
                
                task_json = json.loads(json_str)
                weekly_tasks = task_json.get("weekly_tasks", [])
            except Exception:
                pass
            
            if not weekly_tasks:
                for skill in missing_skills:
                    weekly_tasks.append({
                        "skill": skill,
                        "tasks": [
                            f"Study {skill} fundamentals and core concepts",
                            f"Complete online {skill} tutorial or course",
                            f"Practice {skill} with hands-on exercises",
                            f"Build a small project using {skill}",
                            f"Read {skill} documentation and best practices",
                            f"Join {skill} community and participate in discussions",
                            f"Create a portfolio piece showcasing {skill}"
                        ][:7]
                    })
            
            return {
                "extracted_skills": extracted_skills,
                "missing_skills": missing_skills,
                "weekly_tasks": weekly_tasks
            }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout. Ollama may be slow or unresponsive.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama service. Ensure Ollama is running at http://localhost:11434")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Ollama connection error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

