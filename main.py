from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import re

app = FastAPI(title="YouTube HD Downloader API - Age Bypass")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    quality: str = "1080"

class DownloadResponse(BaseModel):
    success: bool
    title: str
    download_url: str | None = None
    quality: str
    duration: int | None = None
    filesize: str | None = None
    message: str | None = None

def clean_filename(title: str) -> str:
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title[:150]

@app.post("/download")
async def get_download_link(request: DownloadRequest):
    if not request.url or ("youtube.com" not in request.url and "youtu.be" not in request.url):
        raise HTTPException(status_code=400, detail="Vui lòng nhập link YouTube hợp lệ")

    try:
        ydl_opts = {
            'format': f'bestvideo[height<={request.quality}]+bestaudio/best[height<={request.quality}]' 
                      if request.quality != "highest" else 'bestvideo+bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'ios', 'android', 'web_creator'],
                    'skip': ['agegate'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            'age_limit': 0,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)

            # === BẢO VỆ KHÔNG CHO CRASH NoneType ===
            if info is None:
                raise HTTPException(status_code=503, detail="Không thể lấy thông tin video. Video có thể bị age-restricted hoặc private.")

            title = info.get('title', 'video')
            safe_title = clean_filename(title)
            duration = info.get('duration')

            direct_url = None

            # Ưu tiên format đã merge
            if info.get('url') and info.get('ext') in ['mp4', 'mkv', 'webm']:
                direct_url = info['url']
            else:
                formats = info.get('formats', []) or []
                for f in reversed(formats):
                    if (f.get('vcodec') != 'none' and 
                        f.get('acodec') != 'none' and 
                        f.get('url')):
                        direct_url = f['url']
                        break

            if not direct_url:
                raise HTTPException(
                    status_code=503, 
                    detail="Không lấy được link tải trực tiếp. Video có thể bị hạn chế."
                )

            filesize = None
            if info.get('filesize_approx'):
                filesize = f"{info['filesize_approx'] / (1024*1024):.1f} MB"

            return DownloadResponse(
                success=True,
                title=f"{safe_title}.mp4",
                download_url=direct_url,
                quality=f"{request.quality}p",
                duration=duration,
                filesize=filesize,
                message="Thành công"
            )

    except Exception as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["sign in", "login", "age", "restricted", "403", "agegate"]):
            detail = "Video này bị age-restricted hoặc private. API hiện tại trên Vercel chưa bypass được hết."
        else:
            detail = f"Lỗi: {str(e)}"

        raise HTTPException(status_code=500, detail=detail)


@app.get("/")
async def root():
    return {
        "message": "YouTube HD Downloader API đang chạy!",
        "status": "Đã fix lỗi NoneType + tối ưu bypass age-restricted"
    }
