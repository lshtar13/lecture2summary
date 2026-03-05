import os
import uuid
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from app.services import db
from app.services.gemini import GeminiService
from app.services.storage import StorageService

# Load .env
load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Try to initialize DB with retries (wait for Postgres)
    for _ in range(10):
        try:
            await db.init_db()
            break
        except Exception as e:
            print(f"Waiting for DB... {e}")
            await asyncio.sleep(2)
    yield


app = FastAPI(title="Lecture2Summary", lifespan=lifespan)
storage = StorageService()

# ── API Routes ──────────────────────────────────────────

@app.post("/api/upload")
async def upload_and_process(
    audio: UploadFile = File(...),
    pdf: UploadFile | None = File(None),
    title: str = Form(""),
):
    task_id = uuid.uuid4().hex[:12]

    # Determine title
    if not title:
        title = Path(audio.filename).stem if audio.filename else f"Lecture {task_id}"

    # Save audio file to temp then upload to MinIO
    audio_ext = Path(audio.filename).suffix if audio.filename else ".webm"
    audio_filename = f"{task_id}_audio{audio_ext}"
    
    temp_path = f"/tmp/{audio_filename}"
    content = await audio.read()
    with open(temp_path, "wb") as f:
        f.write(content)
    
    storage.upload_file(temp_path, audio_filename)
    os.remove(temp_path)

    # Save PDF if provided
    pdf_filename = None
    if pdf and pdf.filename:
        pdf_filename = f"{task_id}_pdf.pdf"
        pdf_temp = f"/tmp/{pdf_filename}"
        pdf_content = await pdf.read()
        with open(pdf_temp, "wb") as f:
            f.write(pdf_content)
        storage.upload_file(pdf_temp, pdf_filename)
        os.remove(pdf_temp)

    # Create DB record
    await db.create_lecture(task_id, title, audio_filename, pdf_filename)

    # Start background processing
    asyncio.create_task(_process_task(task_id, audio_filename, pdf_filename))

    return {"task_id": task_id, "status": "processing"}


async def _process_task(task_id: str, audio_filename: str, pdf_filename: str | None):
    try:
        # Download files from MinIO to local temp for Gemini
        audio_local = f"/tmp/{audio_filename}"
        storage.download_file(audio_filename, audio_local)
        
        pdf_local = None
        if pdf_filename:
            pdf_local = f"/tmp/{pdf_filename}"
            storage.download_file(pdf_filename, pdf_local)

        gemini = GeminiService()
        # Run in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, gemini.process_audio, audio_local, pdf_local)

        # Cleanup local temp files
        if os.path.exists(audio_local): os.remove(audio_local)
        if pdf_local and os.path.exists(pdf_local): os.remove(pdf_local)

        await db.update_lecture_result(
            task_id,
            summary=result["summary"],
            transcript=result["transcript"],
            full_text=result["full_text"],
        )
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        await db.update_lecture_error(task_id, str(e))


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    lecture = await db.get_lecture(task_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": lecture["status"],
        "title": lecture["title"],
    }


@app.post("/api/retry/{task_id}")
async def retry_task(task_id: str):
    lecture = await db.get_lecture(task_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if lecture["status"] != "error":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    # Reset status in DB
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(db.select(db.Lecture).where(db.Lecture.id == task_id))
        lecture_obj = result.scalar_one_or_none()
        if lecture_obj:
            lecture_obj.status = "processing"
            lecture_obj.summary = None
            await session.commit()

    # Restart background task
    asyncio.create_task(_process_task(task_id, lecture["audio_filename"], lecture["pdf_filename"]))
    
    return {"status": "retrying", "task_id": task_id}


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    lecture = await db.get_lecture(task_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Task not found")
    return lecture


@app.get("/api/history")
async def get_history():
    lectures = await db.get_all_lectures()
    return {"lectures": lectures}


@app.delete("/api/history/{task_id}")
async def delete_history(task_id: str):
    lecture = await db.get_lecture(task_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Task not found")

    # Clean up MinIO files
    if lecture.get("audio_filename"):
        storage.delete_file(lecture["audio_filename"])
    if lecture.get("pdf_filename"):
        storage.delete_file(lecture["pdf_filename"])

    await db.delete_lecture(task_id)
    return {"status": "deleted"}


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    lecture = await db.get_lecture(task_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Task not found")
    if lecture["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # Serve transcript as a text file response (from DB content)
    temp_res = f"/tmp/{task_id}_result.txt"
    with open(temp_res, "w", encoding="utf-8") as f:
        f.write(lecture["full_text"] or "")

    return FileResponse(
        temp_res,
        media_type="text/plain",
        filename=f"{lecture['title']}_transcript.txt",
    )


# ── Static Files (SPA) ─────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
