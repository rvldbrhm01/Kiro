# Kiro Telegram Bot

Bot Telegram berbasis **Anthropic Claude** yang bertindak sebagai AI software engineer — bisa ngobrol soal kode, baca/tulis file di workspace, jalankan script, dan kelola GitHub issues langsung dari Telegram.

---

## Fitur

| Kategori | Kemampuan |
|---|---|
| 💬 **AI Assistant** | Chat coding, debug, review, arsitektur — persona Kiro |
| 📁 **Baca/Tulis Kode** | Baca file & direktori, tulis file baru, patch sebagian file |
| ⚙️ **Jalankan Script** | Eksekusi Python, Node.js, npm, git, dll. di workspace |
| 🐙 **GitHub Issues** | Lihat, label, komen, tutup issue |
| 🔁 **Kiro Triage** | Pipeline lengkap: deteksi duplikat → klasifikasi AI → assign label → komentar |
| 🗑️ **Stale Issues** | Tutup otomatis issue `pending-response` yang tidak aktif 7+ hari |
| 🔒 **Akses Terbatas** | Whitelist Telegram user ID — hanya kamu yang bisa pakai |

---

## Prasyarat

- Python 3.10+
- Node.js 18+ & npm (untuk fitur triage & stale via Kiro scripts)
- Akun Telegram + bot token dari [@BotFather](https://t.me/BotFather)
- API key Anthropic dari [console.anthropic.com](https://console.anthropic.com/)
- GitHub Personal Access Token (untuk fitur GitHub)
- *(Opsional)* AWS credentials untuk fitur triage via Bedrock

---

## Setup

### 1. Clone / siapkan workspace

Pastikan struktur direktori seperti ini:
```
workspace/
├── Kiro/          ← repo Kiro (untuk fitur triage & stale)
│   └── scripts/
└── telegram-bot/  ← direktori ini
```

### 2. Install dependensi Python

```bash
cd telegram-bot
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install dependensi Node.js (untuk fitur Kiro scripts)

```bash
cd ../Kiro/scripts
npm install
```

### 4. Buat file konfigurasi

```bash
cd ../../telegram-bot
cp .env.example .env
```

Edit `.env` dan isi nilai berikut:

| Variabel | Keterangan |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari @BotFather |
| `ANTHROPIC_API_KEY` | API key dari console.anthropic.com |
| `ALLOWED_USER_IDS` | Telegram user ID kamu (cek via [@userinfobot](https://t.me/userinfobot)) |
| `GITHUB_TOKEN` | GitHub PAT dengan scope `repo` |
| `GITHUB_OWNER` | Username GitHub kamu |
| `GITHUB_REPO` | Nama repo default |
| `AWS_ACCESS_KEY_ID` | *(Opsional)* Untuk fitur triage via Bedrock |
| `AWS_SECRET_ACCESS_KEY` | *(Opsional)* Untuk fitur triage via Bedrock |

### 5. Jalankan bot

```bash
python bot.py
```

Kamu akan melihat log seperti:
```
Bot Kiro berjalan dengan model claude-sonnet-4-5-20250929 | User diizinkan: {123456789}
```

Buka Telegram, cari bot kamu, kirim `/start` — selesai!

---

## Perintah Telegram

### Umum
| Perintah | Fungsi |
|---|---|
| `/start` | Salam pembuka |
| `/help` | Daftar perintah |
| `/reset` | Hapus riwayat percakapan |
| `/model` | Tampilkan model Claude aktif |
| `/tools` | Daftar semua tools yang tersedia |

### GitHub
| Perintah | Fungsi |
|---|---|
| `/issues` | Daftar 10 open issues terbaru (repo default) |
| `/issue 42` | Detail issue #42 |
| `/triage 42` | Jalankan pipeline triage Kiro pada issue #42 |
| `/stale` | Tutup semua issue stale (pending-response 7+ hari) |

---

## Contoh Chat

```
Kamu: baca file telegram-bot/tools.py baris 1-50
Kiro: [menampilkan isi file baris 1-50]

Kamu: buatkan unit test untuk fungsi calculate
Kiro: [menulis kode test + penjelasan]

Kamu: triage issue #42
Kiro: [menjalankan pipeline triage, melaporkan hasilnya]

Kamu: jalankan git status di Kiro/scripts
Kiro: [menampilkan output git status]
```

---

## Struktur File

```
telegram-bot/
├── bot.py          # Entry point — Telegram handlers + whitelist akses
├── agent.py        # Loop agent Claude + tool use + memori percakapan
├── tools.py        # Semua tool: kode, GitHub, shell, web search
├── requirements.txt
├── .env.example    # Template konfigurasi
├── .gitignore
└── README.md
```

---

## Menambah Tool Baru

Buka `tools.py` dan:

1. Tulis fungsi Python yang mengembalikan `str` (JSON direkomendasikan)
2. Tambahkan schema JSON ke `TOOL_SCHEMAS`
3. Daftarkan ke `TOOL_IMPLEMENTATIONS`

Agent loop di `agent.py` akan otomatis menemukan dan memanggilnya.

---

## Catatan Keamanan

- **Whitelist user ID**: Bot menolak semua pesan dari user yang tidak ada di `ALLOWED_USER_IDS`
- **Shell terbatas**: `run_shell_command` hanya mengizinkan perintah dari whitelist (`python`, `git`, `npm`, dll.)
- **Sandbox file**: `read_code_file` dan `write_code_file` dibatasi di dalam `WORKSPACE_ROOT`
- **JANGAN** commit file `.env` ke git — sudah ada di `.gitignore`

---

## Catatan & Keterbatasan

- **Memori**: Riwayat percakapan disimpan di memori proses — restart = lupa. Untuk persistensi, ganti dengan Redis atau SQLite
- **Web search**: Menggunakan DuckDuckGo Instant Answer API — hasilnya bagus untuk query tertentu, kurang untuk yang lain. Bisa diganti Tavily/Brave/Serper untuk hasil lebih baik
- **Triage & stale**: Membutuhkan Node.js dan repo `Kiro/scripts` sejajar dengan `telegram-bot/`
- **AWS Bedrock**: Hanya diperlukan untuk fitur triage (klasifikasi issue & deteksi duplikat)
