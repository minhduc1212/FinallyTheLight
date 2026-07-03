import os
import sys
import yaml
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import contextvars
import asyncio

# Ensure parent directory is in path so we can import src modules
sys.path.append(str(Path(__file__).parent.resolve()))

import src.pipeline
from src.pipeline import TranslationPipeline
from src.checkpoint_manager import CheckpointManager
from src.glossary_manager import GlossaryManager
from src.chunker import chunk_text

# Load dotenv
import dotenv
dotenv.load_dotenv()

app = FastAPI(title="Finally The Light — Novel Translator API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ContextVar for logging
current_project_var = contextvars.ContextVar("current_project", default=None)
project_status = {}

# Intercept prints from pipeline
import builtins
def custom_pipeline_print(*args, **kwargs):
    # Print to actual console
    builtins.print(*args, **kwargs)
    
    project = current_project_var.get()
    if not project:
        return
        
    message = " ".join(str(a) for a in args)
    
    if project not in project_status:
        project_status[project] = {
            "status": "translating",
            "current_chunk": 0,
            "total_chunks": 0,
            "step": "Initializing",
            "logs": [],
            "error": None,
            "output_file": None
        }
        
    status = project_status[project]
    status["logs"].append(message)
    if len(status["logs"]) > 200:
        status["logs"] = status["logs"][-200:]
        
    # Check for progress messages
    if "Chunk" in message and "/" in message:
        progress_match = re.search(r"Chunk\s+(\d+)/(\d+)", message)
        if progress_match:
            status["current_chunk"] = int(progress_match.group(1))
            status["total_chunks"] = int(progress_match.group(2))
            
    # Step description
    step_match = re.search(r"Step\s+\d+/\d+:\s*([^-.\n]+)", message)
    if step_match:
        status["step"] = step_match.group(1).strip()
    elif "Verifying similarity" in message:
        status["step"] = "Verifying similarity"
    elif "Splitting into 2 smaller chunks" in message:
        status["step"] = "Splitting chunk"
    elif "completed" in message:
        status["step"] = "Completed chunk"
    elif "Done" in message:
        status["step"] = "Translation finished"
    elif "Resuming progress" in message:
        status["step"] = "Resuming from checkpoint"

# Monkey-patch pipeline
src.pipeline.print = custom_pipeline_print

class SettingsUpdate(BaseModel):
    concurrency: Dict[str, Any]
    features: Dict[str, Any]
    model: Dict[str, Any]
    retry: Dict[str, Any]
    translation: Dict[str, Any]

class TermCreate(BaseModel):
    term: str
    translation: str

class CharacterCreate(BaseModel):
    name: str
    info: str # e.g. translation | role | address

@app.get("/api/genres")
def get_genres():
    genres_path = Path("config/genres.yaml")
    if not genres_path.exists():
        raise HTTPException(status_code=404, detail="genres.yaml not found")
    with open(genres_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

@app.get("/api/settings")
def get_settings():
    settings_path = Path("config/settings.yaml")
    if not settings_path.exists():
        raise HTTPException(status_code=404, detail="settings.yaml not found")
    with open(settings_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

@app.post("/api/settings")
def save_settings(settings: SettingsUpdate):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "w", encoding="utf-8") as f:
        yaml.dump(settings.dict(), f, allow_unicode=True, default_flow_style=False)
    return {"message": "Settings saved successfully"}

@app.get("/api/projects")
def get_projects():
    data_dir = Path("data")
    projects = set()
    if data_dir.exists():
        for p in data_dir.glob("*_glossary.json"):
            projects.add(p.name[:-14]) # Remove _glossary.json
            
    # Also scan checkpoints
    checkpoint_dir = Path("checkpoints")
    if checkpoint_dir.exists():
        for p in checkpoint_dir.iterdir():
            if p.is_dir() and p.name != "__pycache__":
                projects.add(p.name)
                
    return sorted(list(projects))

@app.get("/api/projects/{project}/glossary")
def get_glossary(project: str):
    # Setup glossary manager
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir = settings.get("paths", {}).get("data_dir", "data")
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    return {
        "terms": mgr.get_all(),
        "characters": mgr.get_characters()
    }

@app.post("/api/projects/{project}/glossary/term")
def add_glossary_term(project: str, data: TermCreate):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir = settings.get("paths", {}).get("data_dir", "data")
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        mgr._data["terms"][data.term] = data.translation
        mgr.save()
    return {"message": "Term added/updated successfully"}

@app.delete("/api/projects/{project}/glossary/term/{term}")
def delete_glossary_term(project: str, term: str):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir = settings.get("paths", {}).get("data_dir", "data")
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        if term in mgr._data["terms"]:
            del mgr._data["terms"][term]
            mgr.save()
            return {"message": "Term deleted successfully"}
    raise HTTPException(status_code=404, detail="Term not found")

@app.post("/api/projects/{project}/glossary/character")
def add_glossary_character(project: str, data: CharacterCreate):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir = settings.get("paths", {}).get("data_dir", "data")
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        mgr._data["characters"][data.name] = data.info
        mgr.save()
    return {"message": "Character added/updated successfully"}

@app.delete("/api/projects/{project}/glossary/character/{name}")
def delete_glossary_character(project: str, name: str):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir = settings.get("paths", {}).get("data_dir", "data")
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        if name in mgr._data["characters"]:
            del mgr._data["characters"][name]
            mgr.save()
            return {"message": "Character deleted successfully"}
    raise HTTPException(status_code=404, detail="Character not found")

@app.get("/api/projects/{project}/checkpoints")
def get_project_checkpoints(project: str):
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    cp_dir = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
    mgr = CheckpointManager(project, base_dir=cp_dir)
    checkpoints = mgr.list_checkpoints()
    res = []
    for cp in checkpoints:
        prog = mgr.get_progress(cp)
        if prog:
            res.append({
                "file_stem": cp,
                "current_chunk": prog[0],
                "total_chunks": prog[1]
            })
    return res

async def run_translation_task(
    project: str,
    file_path: Path,
    resume: bool,
    genre: str,
    target_lang: str,
    source_lang: Optional[str] = None
):
    current_project_var.set(project)
    project_status[project] = {
        "status": "translating",
        "current_chunk": 0,
        "total_chunks": 0,
        "step": "Starting pipeline...",
        "logs": [],
        "error": None,
        "output_file": None
    }
    
    try:
        pipeline = TranslationPipeline(
            project=project,
            genre=genre,
            target_lang=target_lang,
            source_lang=source_lang,
            output_dir="output",
        )
        output_path = await pipeline.translate_file(file_path, resume=resume)
        
        project_status[project]["status"] = "completed"
        project_status[project]["output_file"] = output_path.name
        project_status[project]["step"] = "Completed"
    except Exception as e:
        import traceback
        traceback.print_exc()
        project_status[project]["status"] = "failed"
        project_status[project]["error"] = str(e)
        project_status[project]["step"] = "Failed"

@app.post("/api/projects/{project}/translate")
async def start_translation(
    project: str,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    genre: str = Form("default"),
    source_lang: str = Form("auto"),
    target_lang: str = Form("vi"),
    resume: bool = Form(False)
):
    # Verify API key
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY environment variable is not set")

    if project in project_status and project_status[project]["status"] == "translating":
        raise HTTPException(status_code=400, detail="A translation task is already running for this project")

    # Set up directories
    temp_dir = Path("data/temp_inputs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = None
    if file:
        file_path = temp_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
    elif text:
        file_path = temp_dir / f"{project}_input.txt"
        file_path.write_text(text, encoding="utf-8")
    else:
        # Check if there is an active checkpoint we can resume
        if resume:
            settings_path = Path("config/settings.yaml")
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            cp_dir = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
            mgr = CheckpointManager(project, base_dir=cp_dir)
            checkpoints = mgr.list_checkpoints()
            if checkpoints:
                # Use the first checkpoint file stem
                file_stem = checkpoints[0]
                # Look for the input file in data/temp_inputs
                for p in temp_dir.glob(f"{file_stem}.*"):
                    file_path = p
                    break
                if not file_path:
                    # Fallback: assume .txt
                    file_path = temp_dir / f"{file_stem}.txt"
                    if not file_path.exists():
                        file_path.write_text("", encoding="utf-8") # Empty file, just to pass pipeline validation
            else:
                raise HTTPException(status_code=400, detail="No checkpoints found to resume")
        else:
            raise HTTPException(status_code=400, detail="Please provide either text or a file to translate")

    # Start background task
    src_lang_override = None if source_lang == "auto" else source_lang
    asyncio.create_task(run_translation_task(
        project=project,
        file_path=file_path,
        resume=resume,
        genre=genre,
        target_lang=target_lang,
        source_lang=src_lang_override
    ))
    
    return {"message": "Translation started", "project": project}

@app.get("/api/projects/{project}/status")
def get_status(project: str):
    if project not in project_status:
        # Check if there are checkpoints, if so, report idle with checkpoint progress
        settings_path = Path("config/settings.yaml")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        cp_dir = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
        mgr = CheckpointManager(project, base_dir=cp_dir)
        checkpoints = mgr.list_checkpoints()
        
        if checkpoints:
            # Get progress of the first checkpoint
            prog = mgr.get_progress(checkpoints[0])
            if prog:
                return {
                    "status": "idle",
                    "current_chunk": prog[0],
                    "total_chunks": prog[1],
                    "step": "Stopped (Checkpoint available)",
                    "logs": ["Checkpoint found. You can resume this project."],
                    "error": None,
                    "output_file": None
                }
        
        return {
            "status": "idle",
            "current_chunk": 0,
            "total_chunks": 0,
            "step": "Idle",
            "logs": [],
            "error": None,
            "output_file": None
        }
        
    return project_status[project]

@app.get("/api/projects/{project}/download/{filename}")
def download_file(project: str, filename: str):
    output_dir = Path("output")
    file_path = output_dir / filename
    if not file_path.exists():
        # Maybe check glossary report
        if filename == f"{project}_glossary_report.md":
            # Generate it on the fly or load it from data
            settings_path = Path("config/settings.yaml")
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            data_dir = settings.get("paths", {}).get("data_dir", "data")
            mgr = GlossaryManager(project, base_dir=data_dir)
            report_content = mgr.export_report()
            # Save it temporarily
            file_path = output_dir / filename
            output_dir.mkdir(parents=True, exist_ok=True)
            file_path.write_text(report_content, encoding="utf-8")
        else:
            raise HTTPException(status_code=404, detail="File not found")
            
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")

# Serve frontend static files
# Place frontend static files at frontend/
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
