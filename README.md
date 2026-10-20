# DEKA News Agent + JARVIS 📰🤖

Monitoring RSS berita Indonesia–Kamboja otomatis setiap 4 jam, serta chat Telegram via GitHub Actions setiap ~5 menit (jadwal bisa terlambat). Tidak memakai SQLite atau Gemini.

## Setup

1. Di **Settings → Secrets and variables → Actions**, tambahkan `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, dan `GROQ_API_KEY` dari Groq Cloud.
2. Aktifkan GitHub Actions dan beri **Read and write permissions** pada Workflow permissions untuk menyimpan state JSON.
3. Jalankan workflow **DEKA JARVIS Telegram Chat** secara manual sekali untuk tes, lalu kirim `/start` ke bot. Pastikan tidak ada webhook Telegram aktif, karena `getUpdates` tidak bekerja saat webhook aktif.
4. Jalankan **Deka News Research** untuk mengetes monitoring berita.

## Perintah chat

- `/start`, `/help`: bantuan
- `/news`, `/latest`: berita RSS terbaru
- `/status`: status bot
- Teks biasa: pertanyaan ke Groq AI (model default `llama-3.1-8b-instant`)

Tanpa `GROQ_API_KEY`, perintah dasar tetap bisa dipakai.

## File

- `news_agent.py`: monitoring berita dan laporan Telegram
- `sources_ai.py`: pencarian RSS publisher (nama lama; tidak memanggil AI)
- `telegram_chat.py`: polling Telegram, perintah, dan Groq
- `seen_news.json`: fingerprint berita publik
- `telegram_offset.json`: offset polling Telegram, dibuat otomatis lewat GitHub API
- `.github/workflows/news.yml`: monitoring setiap 4 jam
- `.github/workflows/telegram-chat.yml`: polling chat setiap 5 menit

## Batasan & privasi

Repo ini publik. **Jangan simpan riwayat chat atau API key dalam JSON repo**. Yang disimpan untuk chat hanya nomor offset update Telegram. Groq menerima pesan yang dikirim untuk fitur AI. Respons tidak real-time; GitHub Actions dapat terlambat/terlewat. Bot hanya merespons `TELEGRAM_CHAT_ID` yang diizinkan. Perintah `/news` mengambil RSS baru, bukan riwayat percakapan.
