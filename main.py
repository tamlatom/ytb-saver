from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import re

app = FastAPI(title="YouTube HD Downloader API - Age Bypass")

# Cho phép Blogspot gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    quality: str = "1080"   # "720", "1080", hoặc "highest"

class DownloadResponse(BaseModel):
    success: bool
    title: str
    download_url: str
    quality: str
    duration: int | None = None
    filesize: str | None = None
    message: str | None = None

def clean_filename(title: str) -> str:
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title[:150]

@app.post("/download", response_model=DownloadResponse)
async def get_download_link(request: DownloadRequest):
    if not request.url or ("youtube.com" not in request.url and "youtu.be" not in request.url):
        raise HTTPException(status_code=400, detail="Vui lòng nhập link YouTube hợp lệ")

    try:
        # Cấu hình tối ưu bypass age-restricted 2026
        ydl_opts = {
            'format': f'bestvideo[height<={request.quality}]+bestaudio/best[height<={request.quality}]'
                      if request.quality != "highest"
                      else 'bestvideo+bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            
            # === Phần quan trọng để bypass age gate ===
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'ios', 'android', 'web_creator', 'web_embedded'],
                    'skip': ['agegate', 'dash', 'hls'],   # Thử bỏ qua một số kiểm tra
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            # Thêm một số tùy chọn hỗ trợ
            'age_limit': 0,                    # Không giới hạn tuổi từ phía yt-dlp
            'ignoreerrors': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)

            title = info.get('title', 'video')
            safe_title = clean_filename(title)
            duration = info.get('duration')

            # Lấy direct_url
            direct_url = None

            # Ưu tiên format đã merge sẵn
            if info.get('url') and info.get('ext') in ['mp4', 'mkv', 'webm']:
                direct_url = info['url']
            else:
                formats = info.get('formats', [])
                for f in reversed(formats):
                    if (f.get('vcodec') != 'none' and 
                        f.get('acodec') != 'none' and 
                        f.get('url')):
                        direct_url = f['url']
                        break

            if not direct_url:
                raise HTTPException(
                    status_code=503, 
                    detail="Không lấy được link tải. Video có thể bị age-restricted nặng hoặc private."
                )

            filesize = None
            if info.get('filesize_approx'):
                filesize = f"{info['filesize_approx'] / (1024*1024):.1f} MB"

            return DownloadResponse(
                success=True,
                title=f"{safe_title}.mp4",
                download_url=direct_url,
                quality=f"{request.quality}p" if request.quality != "highest" else "Highest",
                duration=duration,
                filesize=filesize,
                message="Thành công (có thể vẫn fail với một số video age-restricted rất nghiêm ngặt)"
            )

    except Exception as e:
        error_msg = str(e).lower()
        
        if any(x in error_msg for x in ["sign in", "login", "age", "verify", "restricted", "403", "agegate"]):
            detail = "Video này yêu cầu đăng nhập (age-restricted). Hiện tại API trên Vercel khó bypass hoàn toàn. Thử link công khai hoặc chuyển sang Railway."
        else:
            detail = f"Lỗi: {str(e)}"

        raise HTTPException(status_code=500, detail=detail)


@app.get("/")
async def root():
    return {
        "message": "YouTube HD Downloader API đang chạy!",
        "note": "Đã tối ưu bypass age-restricted. Vẫn có thể fail với một số video nghiêm ngặt trên Vercel."
    }
