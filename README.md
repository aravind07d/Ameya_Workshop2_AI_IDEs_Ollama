# Resume Skills Analyzer - FastAPI Service with Local LLM

A FastAPI-based service that uses a local Large Language Model (LLM) via Ollama to analyze resumes and extract skills, competencies, and match them with job descriptions.

## Features

- **Health Check Endpoint**: Monitor service status and Ollama connectivity
- **Resume Upload**: Upload and process resume files
- **Skills Analysis**: Analyze resumes using local LLM to extract technical skills, soft skills, experience, and achievements
- **Job Matching**: Optional job description matching to assess resume fit

## Prerequisites

1. **Python 3.8+** installed on your system
2. **Ollama** installed and running locally
   - Download from: https://ollama.ai
   - Install and start the Ollama service
   - Pull a model (e.g., `llama2`): `ollama pull llama2`
3. **Ollama Service** running on `http://localhost:11434`

## Installation

1. **Clone or navigate to the project directory**

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Service

1. **Ensure Ollama is running**:
   - Start Ollama service (usually runs automatically after installation)
   - Verify it's accessible at `http://localhost:11434`

2. **Start the FastAPI server**:
   ```bash
   uvicorn main:app --reload
   ```

3. **Access the service**:
   - API Base URL: `http://localhost:8000`
   - Interactive API Documentation: `http://localhost:8000/docs`
   - Alternative API Documentation: `http://localhost:8000/redoc`

## API Endpoints

### 1. GET /health
Check the health status of the service and Ollama connection.

**Response:**
```json
{
  "status": "healthy",
  "ollama": "connected"
}
```

### 2. POST /upload_resume
Upload a resume file (text file).

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: File upload

**Response:**
```json
{
  "filename": "resume.txt",
  "size": 1234,
  "message": "Resume uploaded successfully",
  "resume_text": "..."
}
```

### 3. POST /analyze_skills
Analyze a resume and extract skills using the local LLM.

**Request Body:**
```json
{
  "resume_text": "Resume content here...",
  "job_description": "Optional job description..."
}
```

**Response:**
```json
{
  "status": "success",
  "analysis": {
    "technical_skills": [...],
    "soft_skills": [...],
    "experience": "...",
    "achievements": [...],
    "match_score": "..."
  }
}
```

## Usage Examples

### Using cURL

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Upload Resume:**
```bash
curl -X POST "http://localhost:8000/upload_resume" -F "file=@resume.txt"
```

**Analyze Skills:**
```bash
curl -X POST "http://localhost:8000/analyze_skills" \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "John Doe\nSoftware Engineer\n5 years experience in Python and FastAPI...",
    "job_description": "Looking for a Python developer with FastAPI experience..."
  }'
```

### Using Python

```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Upload resume
with open("resume.txt", "rb") as f:
    response = requests.post("http://localhost:8000/upload_resume", files={"file": f})
    print(response.json())

# Analyze skills
response = requests.post(
    "http://localhost:8000/analyze_skills",
    json={
        "resume_text": "Your resume text here...",
        "job_description": "Optional job description..."
    }
)
print(response.json())
```

## Configuration

The service uses the following default configuration:
- **Ollama Base URL**: `http://localhost:11434`
- **Default Model**: `llama2`
- **API Port**: `8000` (default for uvicorn)

To change the Ollama model, modify the `model` parameter in the `/analyze_skills` endpoint in `main.py`.

## Troubleshooting

1. **Ollama Connection Error**:
   - Ensure Ollama is installed and running
   - Check if Ollama is accessible at `http://localhost:11434`
   - Verify the model is pulled: `ollama list`

2. **Model Not Found**:
   - Pull the required model: `ollama pull llama2`
   - Or change the model name in `main.py` to match an available model

3. **Port Already in Use**:
   - Change the port: `uvicorn main:app --reload --port 8001`

4. **Import Errors**:
   - Ensure virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

## Project Structure

```
.
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## License

This project is provided as-is for educational and development purposes.

