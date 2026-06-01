import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

app = FastAPI(
    title="YouTube Transcript Extractor API",
    description="Microservice FastAPI untuk mengambil transkrip video YouTube dengan deteksi bahasa otomatis, dukungan fallback, dan fitur penerjemahan otomatis.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mengizinkan CORS agar bisa diakses dari berbagai asal (cross-origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Regular expression untuk mengekstrak Video ID dari berbagai format URL YouTube
YOUTUBE_ID_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
)

def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    Mengekstrak 11-karakter video ID dari string input (bisa berupa ID langsung atau URL YouTube lengkap).
    """
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    match = YOUTUBE_ID_REGEX.search(url_or_id)
    if match:
        return match.group(1)
    return None

class TranscriptSegment(BaseModel):
    text: str = Field(..., description="Teks transkrip pada segmen tertentu")
    start: float = Field(..., description="Waktu mulai dalam detik")
    duration: float = Field(..., description="Durasi segmen dalam detik")

class TranscriptResponse(BaseModel):
    success: bool = Field(..., description="Status keberhasilan operasi")
    video_id: str = Field(..., description="ID dari video YouTube")
    original_language: str = Field(..., description="Bahasa asli transkrip asal")
    retrieved_language: str = Field(..., description="Bahasa transkrip yang berhasil didapatkan")
    is_translated: bool = Field(..., description="Apakah transkrip merupakan hasil terjemahan otomatis")
    was_fallback_used: bool = Field(..., description="Apakah sistem menggunakan fallback bahasa lain")
    is_generated: bool = Field(..., description="Apakah transkrip berupa auto-generated")
    full_text: str = Field(..., description="Seluruh teks transkrip yang digabungkan")
    segments: List[TranscriptSegment] = Field(..., description="Detail segmen transkrip beserta timestamp")

class ErrorResponse(BaseModel):
    success: bool = Field(False)
    error: str = Field(..., description="Pesan error/detail kendala")
    code: str = Field(..., description="Kode error sistem untuk integrasi")

class TranscriptRequest(BaseModel):
    url_or_id: str = Field(..., description="URL video YouTube lengkap atau 11-karakter Video ID", example="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    target_lang: str = Field("id", description="Kode bahasa utama yang diinginkan (ISO 639-1)", example="id")

@app.get("/", include_in_schema=False)
def root():
    """ Mengalihkan halaman utama (/) ke dokumentasi Swagger (/docs) """
    return RedirectResponse(url="/docs")

@app.get("/api/health", response_model=Dict[str, str], tags=["Sistem"])
def health_check():
    """ Cek kesehatan server / microservice """
    return {"status": "healthy", "service": "YouTube Transcript Extractor"}

@app.get("/api/transcript", response_model=TranscriptResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
}, tags=["Transkrip"])
def get_transcript_query(
    video: str = Query(..., description="Video ID atau URL YouTube lengkap", example="dQw4w9WgXcQ"),
    lang: str = Query("id", description="Kode bahasa utama yang ditargetkan (default: 'id' / Indonesia)", example="id")
):
    """
    Mengambil transkrip YouTube dengan deteksi bahasa otomatis, dukungan fallback, dan terjemahan otomatis.
    Metode GET ini ideal untuk integrasi cepat via query string.
    """
    video_id = extract_video_id(video)
    if not video_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "ID Video YouTube tidak valid. Pastikan format URL atau ID sepanjang 11 karakter sudah benar.",
                "code": "INVALID_VIDEO_ID"
            }
        )
    
    return process_transcript_extraction(video_id, lang)

@app.post("/api/transcript", response_model=TranscriptResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
}, tags=["Transkrip"])
def get_transcript_post(payload: TranscriptRequest):
    """
    Mengambil transkrip YouTube dengan deteksi bahasa otomatis, dukungan fallback, dan terjemahan otomatis.
    Metode POST ini menggunakan request body berformat JSON untuk fleksibilitas struktural yang lebih baik.
    """
    video_id = extract_video_id(payload.url_or_id)
    if not video_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "ID Video YouTube tidak valid. Pastikan format URL atau ID sepanjang 11 karakter sudah benar.",
                "code": "INVALID_VIDEO_ID"
            }
        )
    return process_transcript_extraction(video_id, payload.target_lang)

def process_transcript_extraction(video_id: str, target_lang: str):
    """
    Logika utama penarikan transkrip dengan strategi fallback dan penerjemahan.
    """
    # Normalisasi kode bahasa ke huruf kecil
    target_lang = target_lang.lower().strip()
    
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": "Transkrip/subtitle dinonaktifkan untuk video ini oleh pengunggah.",
                "code": "TRANSCRIPTS_DISABLED"
            }
        )
    except VideoUnavailable:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": "Video tidak tersedia atau tidak dapat ditemukan (mungkin dihapus, di-private, atau link salah).",
                "code": "VIDEO_UNAVAILABLE"
            }
        )
    except Exception as e:
         return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Gagal membaca daftar transkrip karena kendala eksternal: {str(e)}",
                "code": "ERROR_LISTING_TRANSCRIPTS"
            }
        )

    transcript = None
    was_fallback_used = False
    original_lang = None
    is_translated = False

    # Langkah 1: Cari transkrip asli dalam target_lang (misal 'id') secara presisi
    try:
        transcript = transcript_list.find_transcript([target_lang])
        original_lang = transcript.language_code
    except NoTranscriptFound:
        pass

    # Langkah 2: Jika gagal, cari bahasa Inggris ('en') sebagai fallback utama
    if not transcript and target_lang != "en":
        try:
            transcript = transcript_list.find_transcript(["en"])
            original_lang = transcript.language_code
            was_fallback_used = True
        except NoTranscriptFound:
            pass

    # Langkah 3: Jika belum ketemu, ambil transkrip pertama yang ada tanpa memandang bahasa (bahasa bawaan pembuat video)
    if not transcript:
        try:
            all_transcripts = list(transcript_list)
            if all_transcripts:
                transcript = all_transcripts[0]
                original_lang = transcript.language_code
                was_fallback_used = True
        except Exception:
            pass

    # Jika semua langkah gagal dan tidak ada transkrip sama sekali
    if not transcript:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": f"Tidak ditemukan transkrip dalam bahasa target ({target_lang}) ataupun bahasa fallback lainnya.",
                "code": "NO_TRANSCRIPT_FOUND"
            }
        )

    # Langkah 4: Jika bahasa transkrip yang didapatkan tidak cocok dengan bahasa target, lakukan auto-translation jika memungkinkan
    final_transcript_obj = transcript
    if transcript.language_code != target_lang:
        if transcript.is_translatable:
            try:
                final_transcript_obj = transcript.translate(target_lang)
                is_translated = True
            except Exception as e:
                # Terjemahan gagal, fallback ke transkrip orisinal yang terpilih tanpa translate
                pass

    # Langkah 5: Unduh data segmen transkrip aktual
    try:
        segments_raw = final_transcript_obj.fetch()
        full_text = " ".join([seg['text'] for seg in segments_raw]).strip()
        
        # Bersihkan spasi atau baris baru ganda di teks segmen
        cleaned_segments = []
        for seg in segments_raw:
            cleaned_segments.append({
                "text": " ".join(seg['text'].split()),
                "start": float(seg['start']),
                "duration": float(seg['duration'])
            })

        return {
            "success": True,
            "video_id": video_id,
            "original_language": original_lang,
            "retrieved_language": final_transcript_obj.language_code,
            "is_translated": is_translated,
            "was_fallback_used": was_fallback_used,
            "is_generated": transcript.is_generated,
            "full_text": full_text,
            "segments": cleaned_segments
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Gagal mengekstrak teks segmen transkrip: {str(e)}",
                "code": "ERROR_FETCHING_SEGMENTS"
            }
        )
