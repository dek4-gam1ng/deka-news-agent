# DEKA News Research Bot 📰

Gratis tanpa API AI berbayar: memantau Google News RSS tentang judi online, penindakan, regulasi, scam, dan WNI di **Indonesia dan Kamboja**. Dikirim ke chat Telegram pribadi melalui **@d3kamencaribot**.

**Catatan:** Ini agregator berbasis kata kunci, **belum memakai model ChatGPT/OpenAI** dan tidak memverifikasi berita secara independen. Hasil bisa tidak lengkap atau keliru; selalu cek tautan sumber.

## Pengaturan

1. Buka **Settings → Secrets and variables → Actions → New repository secret**.
2. Buat `TELEGRAM_BOT_TOKEN` (token dari @BotFather; jangan bagikan atau commit).
3. Buka @d3kamencaribot dan tekan **Start**, lalu dapatkan ID chat pribadi sendiri; simpan sebagai `TELEGRAM_CHAT_ID`. Jangan tempel token ke situs atau bot pihak ketiga.
4. Pastikan GitHub Actions diaktifkan dan **Settings → Actions → General → Workflow permissions** diatur **Read and write permissions** agar file fingerprint berita bisa diperbarui.
5. Buka **Actions → Deka News Research → Run workflow** untuk tes. Setelah itu workflow dijadwalkan setiap 4 jam (UTC; GitHub dapat menunda jadwal).

**Keamanan:** Repo ini public. Hanya fingerprint judul/link berita publik yang disimpan di `seen_news.json`. Jangan simpan data pribadi, token, atau isi chat dalam repo. Secrets tidak perlu dikirim ke ChatGPT.

## Struktur

- `news_agent.py`: RSS, filter berita, deduplikasi, laporan Telegram.
- `requirements.txt`: dependensi Python.
- `.github/workflows/news.yml`: jadwal dan eksekusi GitHub Actions.

**Batasan:** Bot belum membalas perintah Telegram secara real-time. GitHub Actions hanya menjalankan pemeriksaan berkala atau manual melalui UI GitHub.
