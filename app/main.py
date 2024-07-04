from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
from youtube_search import YoutubeSearch
import os
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

# Directorio para almacenar los videos temporalmente
VIDEO_DIR = "app/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

# Diccionario para rastrear los archivos y su tiempo de expiración
video_files = {}

# Configurar el scheduler para limpiar archivos viejos
scheduler = BackgroundScheduler()
scheduler.start()

class VideoRequest(BaseModel):
    query: str

def remove_old_files():
    now = datetime.now()
    for file, expire_time in list(video_files.items()):
        if now > expire_time:
            file_path = os.path.join(VIDEO_DIR, file)
            if os.path.exists(file_path):
                os.remove(file_path)
            del video_files[file]

scheduler.add_job(remove_old_files, 'interval', hours=1)

@app.post("/download/")
async def download_video(request: VideoRequest):
    query = request.query

    if "youtube.com" in query or "youtu.be" in query:
        # Es un enlace de YouTube
        url = query
    else:
        # Realizar búsqueda en YouTube
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            raise HTTPException(status_code=404, detail="Video not found")
        video_id = results[0]['id']
        url = f"https://www.youtube.com/watch?v={video_id}"

    # Descargar el video
    ydl_opts = {
        'outtmpl': os.path.join(VIDEO_DIR, '%(id)s.%(ext)s'),
        'format': 'best'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        video_id = info_dict.get("id")
        ext = info_dict.get("ext")
        filename = f"{video_id}.{ext}"

    # Registrar el archivo y su tiempo de expiración
    expire_time = datetime.now() + timedelta(hours=24)
    video_files[filename] = expire_time

    # Generar el enlace reproducible
    link = f"https://ytdlapi.onrender.com/videos/{filename}"

    return {"url": link}

@app.get("/videos/{filename}")
async def serve_video(filename: str):
    file_path = os.path.join(VIDEO_DIR, filename)
    if os.path.exists(file_path):
        return StreamingResponse(open(file_path, "rb"), media_type="video/mp4")
    else:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
