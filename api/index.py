import re
import os
import tempfile
from typing import Optional, List, Dict
from fastapi import FastAPI, Query, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

app = FastAPI(
    title="YouTube Transcript Extractor API",
    description="API FastAPI sederhana untuk mengekstrak transkrip dari video YouTube secara instan dengan fitur terjemahan otomatis.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Konfigurasi CORS agar API dapat diakses dari domain mana pun
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Regex sekali jalan untuk mengekstrak Video ID (11 karakter) dari URL YouTube apa pun
YOUTUBE_ID_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
)

def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    Ekstrak 11 digit Video ID dari string masukan (baik URL penuh maupun ID langsung).
    """
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    # Jika masukan sudah berupa ID 11 karakter yang valid
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    match = YOUTUBE_ID_REGEX.search(url_or_id)
    return match.group(1) if match else None


# Schema masukan untuk metode POST
class TranscriptRequest(BaseModel):
    url_or_id: str = Field(..., description="ID video atau URL video YouTube lengkap", example="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    target_lang: str = Field("id", description="Kode bahasa target (default: 'id' untuk Bahasa Indonesia)", example="id")
    proxy: Optional[str] = Field(None, description="URL proxy kustom jika diperlukan (opsional)", example="http://username:password@proxyserver.com:8080")
    cookies: Optional[str] = Field(None, description="Teks cookie Netscape untuk bypass pemblokiran (opsional)", example=None)


@app.get("/", include_in_schema=False)
def root():
    # Arahkan halaman utama ke Swagger UI docs agar interaktif
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["Sistem"])
def health_check():
    return {"status": "healthy", "service": "YouTube Transcript Extractor"}


@app.get("/api/transcript", tags=["Transkrip"])
def get_transcript_query(
    video: str = Query(..., description="Video ID atau URL YouTube lengkap"),
    lang: str = Query("id", description="Kode bahasa target (contoh: 'id', 'en')"),
    proxy: Optional[str] = Query(None, description="URL proxy kustom (opsional)"),
    cookies: Optional[str] = Query(None, description="Teks cookie Netscape (opsional)")
):
    """
    Mengambil transkrip YouTube via GET Query string.
    """
    video_id = extract_video_id(video)
    if not video_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "ID Video YouTube tidak valid. Pastikan URL atau ID video benar.",
                "code": "INVALID_VIDEO_ID"
            }
        )
    return process_transcript(video_id, lang, proxy, cookies)


@app.post("/api/transcript", tags=["Transkrip"])
def get_transcript_post(payload: TranscriptRequest):
    """
    Mengambil transkrip YouTube via POST dengan request body JSON.
    """
    video_id = extract_video_id(payload.url_or_id)
    if not video_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "ID Video YouTube tidak valid. Pastikan URL atau ID video benar.",
                "code": "INVALID_VIDEO_ID"
            }
        )
    return process_transcript(video_id, payload.target_lang, payload.proxy, payload.cookies)


def process_transcript(video_id: str, target_lang: str, request_proxy: Optional[str], request_cookies: Optional[str]):
    """
    Fungsi utama untuk mengambil transkrip video YouTube secara aman dengan sistem fallback bahasa
    dan fitur terjemahan otomatis.
    """
    target_lang = target_lang.lower().strip()
    
    # 1. Konfigurasi Proxy (untuk menghindari IP ban / 403 Forbidden)
    proxy_url = request_proxy or os.getenv("YOUTUBE_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # 2. Konfigurasi Cookies via file temporer (untuk memverifikasi akun / mencegah pembatasan)
    cookies_content = request_cookies or os.getenv("YOUTUBE_COOKIES")
    cookies_file_path = None
    
    if cookies_content and cookies_content.strip():
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(cookies_content)
            cookies_file_path = temp_path
        except Exception as e:
            print(f"[Warning] Gagal memuat cookie sementara: {str(e)}")

    try:
        # Step 1: Dapatkan semua daftar transkrip yang tersedia dari video ini
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(
                video_id, 
                proxies=proxies, 
                cookies=cookies_file_path
            )
        except TranscriptsDisabled:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "Transkrip/subtitle dinonaktifkan atau tidak tersedia untuk video ini.",
                    "code": "TRANSCRIPTS_DISABLED"
                }
            )
        except VideoUnavailable:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": "Video YouTube tidak tersedia (mungkin dihapus, di-private, atau link salah).",
                    "code": "VIDEO_UNAVAILABLE"
                }
            )
        except Exception as e:
            err_msg = str(e)
            user_friendly_err = f"Gagal mengambil transkrip: Encountered error: {err_msg}"
            err_code = "SERVER_ERROR"
            
            # Deteksi apakah IP diblokir oleh YouTube (Sangat umum terjadi pada penyedia Cloud seperti Vercel/Render)
            if any(hint in err_msg for hint in ["RequestBlocked", "IpBlocked", "Too Many Requests", "403", "429"]):
                user_friendly_err = (
                    "Permintaan diblokir oleh YouTube (Error 403 / IP Blocked). "
                    "Hal ini terjadi karena IP publik serverless/cloud hosting (seperti Vercel) sering diblokir secara massal oleh YouTube. "
                    "Solusi: Gunakan parameter 'proxy' dengan proxy residensial aktif, "
                    "atau unggah cookie browser Anda ke parameter 'cookies_txt' agar dikenali sebagai pengguna manusia."
                )
                err_code = "YOUTUBE_IP_BLOCKED"
                
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": user_friendly_err,
                    "code": err_code
                }
            )

        # Step 2: Cari transkrip yang paling tepat menggunakan strategi fallback cerdas
        selected_transcript = None
        was_fallback_used = False
        original_lang = None
        is_translated = False

        # 1. Coba cari bahasa target langsung (misalnya Bahasa Indonesia 'id')
        try:
            selected_transcript = transcript_list.find_transcript([target_lang])
            original_lang = selected_transcript.language_code
        except NoTranscriptFound:
            pass

        # 2. Jika tidak ada, coba cari bahasa Inggris ('en') sebagai fallback utama
        if not selected_transcript and target_lang != "en":
            try:
                selected_transcript = transcript_list.find_transcript(["en"])
                original_lang = selected_transcript.language_code
                was_fallback_used = True
            except NoTranscriptFound:
                pass

        # 3. Jika masih tidak ada, ambil bahasa pertama apa pun yang tersedia di video tersebut
        if not selected_transcript:
            try:
                all_transcripts = list(transcript_list)
                if all_transcripts:
                    selected_transcript = all_transcripts[0]
                    original_lang = selected_transcript.language_code
                    was_fallback_used = True
            except Exception:
                pass

        # Jika sama sekali tidak ada transkrip yang ditemukan
        if not selected_transcript:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": f"Tidak ditemukan transkrip dalam bahasa target ({target_lang}) maupun bahasa cadangan lainnya.",
                    "code": "NO_TRANSCRIPT_FOUND"
                }
            )

        # Step 3: Jika bahasa asli berbeda dengan bahasa target, manfaatkan auto-translate YouTube
        final_transcript_obj = selected_transcript
        if selected_transcript.language_code != target_lang:
            if selected_transcript.is_translatable:
                try:
                    final_transcript_obj = selected_transcript.translate(target_lang)
                    is_translated = True
                except Exception:
                    # Jika penerjemahan otomatis gagal, pakai bahasa asli video apa adanya
                    pass

        # Step 4: Tarik data teks per-segmen dan gabungkan
        try:
            raw_segments = final_transcript_obj.fetch()
            
            # Format pembersihan segmen
            cleaned_segments = []
            for item in raw_segments:
                cleaned_segments.append({
                    "text": " ".join(item['text'].split()), # merapikan whitespace
                    "start": float(item['start']),
                    "duration": float(item['duration'])
                })

            full_text = " ".join([seg['text'] for seg in cleaned_segments]).strip()

            return {
                "success": True,
                "video_id": video_id,
                "original_language": original_lang,
                "retrieved_language": final_transcript_obj.language_code,
                "is_translated": is_translated,
                "was_fallback_used": was_fallback_used,
                "is_generated": selected_transcript.is_generated,
                "full_text": full_text,
                "segments": cleaned_segments
            }
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": f"Gagal mengekstrak teks segmen transkrip: {str(e)}",
                    "code": "SEGMENT_FETCH_ERROR"
                }
            )

    finally:
        # Selalu hapus file cookies sementara agar tidak memakan memori disk
        if cookies_file_path and os.path.exists(cookies_file_path):
            try:
                os.remove(cookies_file_path)
            except Exception:
                pass
