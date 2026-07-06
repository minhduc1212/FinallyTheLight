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
BASE_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BASE_DIR))

import src.pipeline
from src.pipeline import TranslationPipeline
from src.checkpoint_manager import CheckpointManager
from src.glossary_manager import GlossaryManager
from src.chunker import chunk_text

def validate_project_name(project: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]+$", project):
        raise HTTPException(status_code=400, detail="Tên dự án không hợp lệ. Chỉ chấp nhận chữ cái, số, gạch dưới và gạch ngang.")
    return project

def validate_novel_name(novel: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_.-]+$", novel):
        raise HTTPException(status_code=400, detail="Tên tiểu thuyết không hợp lệ.")
    return novel

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
project_tasks = {}

# Intercept prints globally to prevent UnicodeEncodeError on Windows
import builtins
original_print = builtins.print

def safe_print(*args, **kwargs):
    message = " ".join(str(a) for a in args)
    
    project = current_project_var.get()
    if project:
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

    try:
        original_print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback to encoding-safe print for Windows CP1252 consoles
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            safe_args = [str(arg).encode(encoding, errors='replace').decode(encoding) for arg in args]
            original_print(*safe_args, **kwargs)
        except Exception:
            pass

# Globally overwrite builtins.print
builtins.print = safe_print
src.pipeline.print = safe_print

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
    genres_path = BASE_DIR / "config" / "genres.yaml"
    if not genres_path.exists():
        raise HTTPException(status_code=404, detail="genres.yaml not found")
    with open(genres_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

@app.get("/api/settings")
def get_settings():
    settings_path = BASE_DIR / "config" / "settings.yaml"
    if not settings_path.exists():
        raise HTTPException(status_code=404, detail="settings.yaml not found")
    with open(settings_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

@app.post("/api/settings")
def save_settings(settings: SettingsUpdate):
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "w", encoding="utf-8") as f:
        yaml.dump(settings.dict(), f, allow_unicode=True, default_flow_style=False)
    return {"message": "Settings saved successfully"}

@app.get("/api/projects")
def get_projects():
    projects = set()
    data_dir = BASE_DIR / "data"
    if data_dir.exists():
        for p in data_dir.glob("*_glossary.json"):
            projects.add(p.name[:-14])
            
    checkpoint_dir = BASE_DIR / "checkpoints"
    if checkpoint_dir.exists():
        for p in checkpoint_dir.iterdir():
            if p.is_dir() and p.name != "__pycache__":
                projects.add(p.name)
                
    p_dir = BASE_DIR / "data" / "projects"
    if p_dir.exists():
        for d in p_dir.iterdir():
            if d.is_dir():
                projects.add(d.name)
                
    return sorted(list(projects))

@app.post("/api/projects/{project}")
def create_project(project: str):
    validate_project_name(project)
    p_dir = BASE_DIR / "data" / "projects" / project / "novels"
    p_dir.mkdir(parents=True, exist_ok=True)
    return {"message": "Project created"}

import shutil
@app.delete("/api/projects/{project}")
def delete_project(project: str):
    validate_project_name(project)
    # delete novels
    p_dir = BASE_DIR / "data" / "projects" / project
    if p_dir.exists():
        shutil.rmtree(p_dir, ignore_errors=True)
    # delete glossary
    g_file = BASE_DIR / "data" / f"{project}_glossary.json"
    if g_file.exists():
        g_file.unlink()
    # delete checkpoints
    c_dir = BASE_DIR / "checkpoints" / project
    if c_dir.exists():
        shutil.rmtree(c_dir, ignore_errors=True)
    return {"message": "Project deleted"}

@app.get("/api/projects/{project}/glossary")
def get_glossary(project: str):
    validate_project_name(project)
    # Setup glossary manager
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir_path = settings.get("paths", {}).get("data_dir", "data")
    data_dir = str(BASE_DIR / data_dir_path)
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    return {
        "terms": mgr.get_all(),
        "characters": mgr.get_characters()
    }

@app.post("/api/projects/{project}/glossary/term")
def add_glossary_term(project: str, data: TermCreate):
    validate_project_name(project)
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir_path = settings.get("paths", {}).get("data_dir", "data")
    data_dir = str(BASE_DIR / data_dir_path)
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        mgr._data["terms"][data.term] = data.translation
        mgr.save()
    return {"message": "Term added/updated successfully"}

@app.delete("/api/projects/{project}/glossary/term/{term}")
def delete_glossary_term(project: str, term: str):
    validate_project_name(project)
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir_path = settings.get("paths", {}).get("data_dir", "data")
    data_dir = str(BASE_DIR / data_dir_path)
    
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
    validate_project_name(project)
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir_path = settings.get("paths", {}).get("data_dir", "data")
    data_dir = str(BASE_DIR / data_dir_path)
    
    mgr = GlossaryManager(project, base_dir=data_dir)
    with mgr.lock:
        mgr._data = mgr._load()
        mgr._data["characters"][data.name] = data.info
        mgr.save()
    return {"message": "Character added/updated successfully"}

@app.delete("/api/projects/{project}/glossary/character/{name}")
def delete_glossary_character(project: str, name: str):
    validate_project_name(project)
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    data_dir_path = settings.get("paths", {}).get("data_dir", "data")
    data_dir = str(BASE_DIR / data_dir_path)
    
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
    validate_project_name(project)
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    cp_dir_path = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
    cp_dir = str(BASE_DIR / cp_dir_path)
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
            output_dir=str(BASE_DIR / "output"),
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


@app.get("/api/projects/{project}/novels")
def get_novels(project: str):
    validate_project_name(project)
    temp_dir = BASE_DIR / "data" / "projects" / project / "novels"
    novels = []
    if temp_dir.exists():
        for p in temp_dir.glob("*.*"):
            if p.is_file():
                novels.append(p.name)
    return novels

@app.post("/api/projects/{project}/novels")
async def upload_novel(
    project: str,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    validate_project_name(project)
    temp_dir = BASE_DIR / "data" / "projects" / project / "novels"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if file:
        validate_novel_name(file.filename)
        file_path = temp_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
        return {"message": "Uploaded", "novel": file.filename}
    elif text:
        file_path = temp_dir / f"{project}_input.txt"
        file_path.write_text(text, encoding="utf-8")
        return {"message": "Saved", "novel": f"{project}_input.txt"}
    raise HTTPException(status_code=400, detail="Provide text or file")


@app.delete("/api/projects/{project}/novels/{novel}")
def delete_novel(project: str, novel: str):
    validate_project_name(project)
    validate_novel_name(novel)
    file_path = BASE_DIR / "data" / "projects" / project / "novels" / novel
    if file_path.exists():
        file_path.unlink()
    return {"message": "Novel deleted"}

@app.get("/api/projects/{project}/novels/{novel}/chunks")
def get_chunks(project: str, novel: str, page: int = 1, limit: int = 50):
    validate_project_name(project)
    validate_novel_name(novel)
    file_path = BASE_DIR / "data" / "projects" / project / "novels" / novel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Novel not found")
        
    text = file_path.read_text(encoding="utf-8")
    
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
        
    chunk_size = settings.get("translation", {}).get("chunk_size", 2500)
    # Detect language using the same logic or just use auto
    from src.chunker import chunk_text, detect_script
    detected_lang = detect_script(text)
    chunks = chunk_text(text, chunk_size, source_lang=detected_lang)
    
    # Load checkpoint
    cp_dir_path = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
    cp_dir = str(BASE_DIR / cp_dir_path)
    mgr = CheckpointManager(project, base_dir=cp_dir)
    checkpoint = mgr.load(file_path.stem)
    
    translated = {}
    failed = {}
    if checkpoint:
        translated = checkpoint.get("translated_chunks", {})
        failed = checkpoint.get("failed_chunks", {})
        
    total = len(chunks)
    start_idx = (page - 1) * limit
    end_idx = min(start_idx + limit, total)
    
    result = []
    for i in range(start_idx, end_idx):
        status = "pending"
        trans_text = ""
        if str(i) in translated:
            status = "completed"
            trans_text = translated[str(i)]
        elif str(i) in failed:
            status = "failed"
            trans_text = failed[str(i)]
            
        result.append({
            "id": i,
            "original": chunks[i],
            "translated": trans_text,
            "status": status
        })
        
    return {
        "total_chunks": total,
        "page": page,
        "limit": limit,
        "chunks": result
    }

class TranslateChunksRequest(BaseModel):
    target_chunks: Optional[List[int]] = None
    genre: str = "default"
    source_lang: str = "auto"
    target_lang: str = "vi"
    resume: bool = True

@app.post("/api/projects/{project}/novels/{novel}/translate_chunks")
async def translate_chunks(
    project: str,
    novel: str,
    req: TranslateChunksRequest
):
    validate_project_name(project)
    validate_novel_name(novel)
    file_path = BASE_DIR / "data" / "projects" / project / "novels" / novel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Novel not found")
        
    if project in project_status and project_status[project]["status"] == "translating":
        raise HTTPException(status_code=400, detail="A translation task is already running")
        
    src_lang_override = None if req.source_lang == "auto" else req.source_lang
    
    # We use a custom task that passes target_chunks
    async def custom_task():
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
                genre=req.genre,
                target_lang=req.target_lang,
                source_lang=src_lang_override,
                output_dir=str(BASE_DIR / "output"),
            )
            output_path = await pipeline.translate_file(file_path, resume=req.resume, target_chunks=req.target_chunks)
            project_status[project]["status"] = "completed"
            project_status[project]["output_file"] = output_path.name
            project_status[project]["step"] = "Completed"
        except Exception as e:
            import traceback
            traceback.print_exc()
            project_status[project]["status"] = "failed"
            project_status[project]["error"] = str(e)
            project_status[project]["step"] = "Failed"

    task = asyncio.create_task(custom_task())
    project_tasks[project] = task
    return {"message": "Translation started"}

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
    validate_project_name(project)
    # Verify API key
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY environment variable is not set")

    if project in project_status and project_status[project]["status"] == "translating":
        raise HTTPException(status_code=400, detail="A translation task is already running for this project")

    # Set up directories
    temp_dir = BASE_DIR / "data" / "projects" / project / "novels"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = None
    if file:
        validate_novel_name(file.filename)
        file_path = temp_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
    elif text:
        file_path = temp_dir / f"{project}_input.txt"
        file_path.write_text(text, encoding="utf-8")
    else:
        # Check if there is an active checkpoint we can resume
        if resume:
            settings_path = BASE_DIR / "config" / "settings.yaml"
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            cp_dir_path = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
            cp_dir = str(BASE_DIR / cp_dir_path)
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
    task = asyncio.create_task(run_translation_task(
        project=project,
        file_path=file_path,
        resume=resume,
        genre=genre,
        target_lang=target_lang,
        source_lang=src_lang_override
    ))
    project_tasks[project] = task
    
    return {"message": "Translation started", "project": project}

@app.get("/api/projects/{project}/status")
def get_status(project: str):
    validate_project_name(project)
    if project not in project_status:
        # Check if there are checkpoints, if so, report idle with checkpoint progress
        settings_path = BASE_DIR / "config" / "settings.yaml"
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        cp_dir_path = settings.get("paths", {}).get("checkpoint_dir", "checkpoints")
        cp_dir = str(BASE_DIR / cp_dir_path)
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
    validate_project_name(project)
    if not re.match(r"^[a-zA-Z0-9_.-]+$", filename):
        raise HTTPException(status_code=400, detail="Tên tệp không hợp lệ")
    output_dir = BASE_DIR / "output"
    file_path = output_dir / filename
    if not file_path.exists():
        # Maybe check glossary report
        if filename == f"{project}_glossary_report.md":
            # Generate it on the fly or load it from data
            settings_path = BASE_DIR / "config" / "settings.yaml"
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            data_dir_path = settings.get("paths", {}).get("data_dir", "data")
            data_dir = str(BASE_DIR / data_dir_path)
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
frontend_dir = BASE_DIR.parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.post("/api/projects/{project}/cancel")
def cancel_translation(project: str):
    validate_project_name(project)
    if project in project_tasks:
        project_tasks[project].cancel()
        if project in project_status:
            project_status[project]["status"] = "failed"
            project_status[project]["step"] = "Đã hủy"
            project_status[project]["error"] = "User cancelled"
        return {"message": "Cancelled"}
    return {"message": "No active task"}
