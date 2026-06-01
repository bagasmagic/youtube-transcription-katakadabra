# YouTube Transcript Extractor API (FastAPI Microservice)

Layanan microservice berbasis **FastAPI (Python)** untuk mengekstraksi transkrip (subtitle) dari video YouTube secara instan dengan fitur pendeteksi bahasa otomatis, sistem fallback yang fleksibel, dan terjemahan otomatis terintegrasi. 

Layanan ini dirancang khusus untuk berjalan sebagai API/backend mandiri tanpa UI, siap dideploy secara instan ke serverless platform seperti **Vercel** atau dipasang di VPS menggunakan Docker / Uvicorn.

---

## ✨ Fitur Utama

- **Deteksi & Ekstraksi Cerdas**: Otomatis mendeteksi bahasa asli video atau transkrip bawaan (baik buatan manusia maupun auto-generated).
- **Strategi Fallback bertingkat**:
  1. Berusaha mengambil transkrip bahasa utama yang diminta (contoh: Bahasa Indonesia `id`).
  2. Jika tidak ada, otomatis jatuh kembali ke Bahasa Inggris (`en`) sebagai fallback utama.
  3. Jika masih belum ditemukan, mengambil bahasa default pertama apa pun yang tersedia yang ada di video tersebut.
- **Penerjemahan Otomatis (Auto-Translation)**: Bila bahasa transkrip yang didapatkan tidak sesuai dengan bahasa target, sistem akan menggunakan API penerjemahan bawaan YouTube untuk menerjemahkannya ke bahasa target (misal: menerjemahkan transkrip Korea atau Inggris langsung ke Bahasa Indonesia).
- **Dua Metode Integrasi**: Mendukung pemicu melalui `GET` (query string) dan `POST` (request body JSON).
- **Response Kaya Informasi**: Output menyajikan seluruh teks utuh menggabungkan semua bagian (`full_text`) serta daftar segmen ber-timestamp detail (`segments`) berisi teks, waktu mulai, dan durasi masing-masing segmen.
- **Auto-Generated Swagger Docs**: Dilengkapi dokumentasi interaktif bawaan di `/docs` (Swagger UI) dan `/redoc` (ReDoc) untuk kemudahan pengujian API secara langsung.

---

## 📂 Struktur Berkas Proyek

- **`/api/index.py`**: Berisi keseluruhan logika microservice FastAPI secara modular.
- **`/requirements.txt`**: Daftar dependensi Python yang dibutuhkan untuk menjalankan layanan.
- **`/vercel.json`**: Konfigurasi deployment serverless Vercel agar otomatis mendeteksi fungsionalitas runtime Python di folder `/api`.

---

## 🛠️ Cara Menjalankan Layanan Secara Lokal

Untuk menguji layanan di komputer lokal Anda, lakukan langkah-langkah berikut:

### 1. Prasyarat
Pastikan komputer Anda sudah terinstal **Python 3.9** atau versi lebih baru.

### 2. Kloning & Buat Virtual Environment
Buat folder lingkungan virtual agar lingkungan dependensi terisolasi dengan rapi:
```bash
# Buat Virtual Environment
python -m venv venv

# Aktifkan di macOS/Linux
source venv/bin/activate

# Atau aktifkan di Windows (Command Prompt)
venv\Scripts\activate
```

### 3. Instal Dependensi
```bash
pip install -r requirements.txt
```

### 4. Jalankan Server FastAPI menggunakan Uvicorn
```bash
uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload
```
Server lokal Anda akan berjalan di `http://localhost:8000`. Buka browser dan pergi ke `http://localhost:8000/docs` untuk membuka dokumentasi interaktif Swagger UI.

---

## 🚀 Panduan Deploy ke Vercel (Gratis & Cepat)

Karena repositori ini sudah dilengkapi berkas `vercel.json` dan struktur folder `/api` standar, Anda dapat mendeploy-nya langsung secara gratis:

1. **Push Proyek ke GitHub Anda**:
   Buat repositori baru di GitHub, lalu commit dan dorong seluruh berkas ini ke sana.
2. **Sambungkan ke Vercel**:
   - Masuk atau daftar di [Vercel](https://vercel.com).
   - Klik **Add New Project** lalu pilih repositori GitHub tempat Anda menyimpan berkas ini.
   - Vercel akan secara otomatis mendeteksi berkas `vercel.json` dan `requirements.txt`.
   - Klik **Deploy**.
3. **Selesai!** Vercel akan menghasilkan domain produksi HTTPS untuk microservice Anda.

---

## 🚀 Dokumentasi Penggunaan API

### 1. Endpoint Kesehatan Layanan (Health Check)
Memastikan layanan aktif dengan baik.

- **URL**: `/api/health`
- **Method**: `GET`
- **Format Respon**:
  ```json
  {
    "status": "healthy",
    "service": "YouTube Transcript Extractor"
  }
  ```

---

### 2. Mengambil Transkrip (Metode GET)
Metode tercepat menggunakan parameter query untuk menarik transkrip langsung.

- **URL**: `/api/transcript`
- **Method**: `GET`
- **Parameter URL / Query String**:
  - `video` (Wajib, berupa 11-karakter ID Video ATAU URL Video Youtube lengkap)
  - `lang` (Opsional, kode bahasa target ISO 639-1, default ke `id` jika tidak disertakan)
  - `proxy` (Opsional, URL proxy kustom gratis / berbayar Anda seperti `http://user:pass@domain:port`)
  - `cookies` (Opsional, string teks cookie berformat Netscape untuk bypass age-restriction / rate-limit)
  
- **Contoh Permintaan**:
  ```http
  GET /api/transcript?video=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=id&proxy=http://username:password@proxyserver.com:8080
  ```

---

### 3. Mengambil Transkrip (Metode POST)
Lebih disarankan untuk integrasi sistem yang lebih rapi karena parameter dibungkus dalam JSON payload dan memfasilitasi pengiriman data cookie yang panjang.

- **URL**: `/api/transcript`
- **Method**: `POST`
- **Header**: `Content-Type: application/json`
- **JSON Request Body**:
  ```json
  {
    "url_or_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "target_lang": "id",
    "proxy": "http://username:password@proxyserver.com:8080",
    "cookies": "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t..."
  }
  ```

---

### 📥 Format Respon Sukses (JSON)
Respons yang kembali ke sistem Anda akan mencakup informasi metadata lengkap mengenai proses fallback serta teks utuh transkrip:

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "original_language": "en",
  "retrieved_language": "id",
  "is_translated": true,
  "was_fallback_used": true,
  "is_generated": true,
  "full_text": "gadis tak asing lagi bagimu kau tahu peraturannya begitu pula aku komitmen penuh adalah yang kupikirkan kau tak akan mendapatkan ini dari pria lain saja...",
  "segments": [
    {
      "text": "gadis tak asing lagi bagimu",
      "start": 0.12,
      "duration": 4.15
    },
    {
      "text": "kau tahu peraturannya begitu pula aku",
      "start": 4.27,
      "duration": 3.8
    }
  ]
}
```

#### Penjelasan Bidang Respons:
- `original_language`: Bahasa asli bawaan pertama dari transkrip video tersebut yang ditemukan (sebelum diterjemahkan).
- `retrieved_language`: Bahasa transkrip final yang berhasil diunduh (misal `id` sesudah diterjemahkan).
- `is_translated`: `true` apabila video aslinya tidak punya subtitle bahasa target sehingga sistem menggunakan fitur auto-translate dari YouTube secara otomatis.
- `was_fallback_used`: `true` apabila video tidak langsung menyediakan bahasa target di penelusuran pertama, sehingga harus memakai fallback bahasa lain (seperti `en`) terlebih dahulu sebelum proses lanjut.
- `is_generated`: `true` jika transkrip yang didapatkan adalah hasil transkripsi otomatis suara video oleh YouTube AI, bukan unggahan manual manusia.

---

### 📥 Format Respon Error (JSON)
Bila terjadi kesalahan, status HTTP non-200 akan dikembalikan bersama kode error spesifik:

```json
{
  "success": false,
  "error": "Transkrip/subtitle dinonaktifkan untuk video ini oleh pengunggah.",
  "code": "TRANSCRIPTS_DISABLED"
}
```

#### Daftar Kode Error Penting untuk Diatasi:
- `INVALID_VIDEO_ID`: Format URL YouTube tidak dikenali atau ID tidak memenuhi standar 11 karakter.
- `TRANSCRIPTS_DISABLED`: Transkrip dinonaktifkan oleh pemilik video sehingga tidak ada subtitle apa pun yang bisa dibaca.
- `VIDEO_UNAVAILABLE`: Video tidak dapat diakses atau diblokir/dihapus karena alasan hak cipta/setelan privasi.
- `NO_TRANSCRIPT_FOUND`: Tidak ditemukan transkrip dalam bahasa target dan tidak ada bahasa alternatif yang layak untuk diproses.
- `SERVER_ERROR_...`: Kendala koneksi atau batas rate-limit dari server eksternal YouTube.
