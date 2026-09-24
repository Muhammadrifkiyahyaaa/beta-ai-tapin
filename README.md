# BETA AI — Bekantan Tapin AI

Chatbot tanya-jawab seputar pariwisata Kabupaten Tapin, Kalimantan Selatan. Dibangun sebagai alat advokasi pariwisata Tapin, dengan jawaban yang digroundingkan ke hasil pencarian internet real-time (bukan mengarang), supaya informasinya tetap relevan dan bisa dipertanggungjawabkan.

## ✨ Fitur

- **Tanya jawab seputar Tapin** — wisata alam, UMKM/produk lokal, tradisi & budaya, kuliner khas, sejarah, dan topik terkait lainnya. Jawaban digroundingkan ke hasil pencarian web (Tavily) yang sudah difilter supaya benar-benar membahas Kabupaten Tapin.
- **Peta interaktif** — tempat yang disebut dalam jawaban otomatis di-geocode dan ditampilkan di peta.
- **Link "Buka di Google Maps"** — setiap tempat di peta bisa langsung dibuka di Google Maps.
- **Info cuaca terkini** — kondisi cuaca real-time area Kabupaten Tapin (sumber: Open-Meteo), ditampilkan otomatis beserta peringatan hujan saat pertanyaan menyinggung rencana jalan-jalan/wisata alam/outdoor.
- **Chat pakai suara (voice input)** — rekam pertanyaan lewat suara, ditranskripsi otomatis (Groq Whisper) lalu diproses seperti chat teks biasa.
- **Dukungan Bahasa Inggris** — otomatis mendeteksi bahasa pertanyaan (Indonesia/Inggris) dan menjawab dalam bahasa yang sama.
- **Perencana itinerary wisata** — buat rencana perjalanan multi-hari otomatis berdasarkan minat yang dipilih.
- **Kalkulator estimasi budget** — estimasi kasar biaya kunjungan (transportasi, makan, penginapan, oleh-oleh).
- **Kuis "Wisata Cocokmu"** — rekomendasi tempat wisata personal berdasarkan profil/gaya jalan-jalan user.
- **Kartu pengingat kebersihan (#JagaKebersihan)** — muncul otomatis di konteks wisata alam/itinerary untuk mengingatkan kebersihan destinasi.
- **Filter topik & lokasi** — pertanyaan di luar topik pariwisata/UMKM/budaya Tapin (politik, cafe modern, dll.) otomatis ditolak dengan sopan, supaya cakupan chatbot tetap fokus.

## 🛠️ Tech Stack

| Komponen | Tools |
|---|---|
| Frontend/UI | [Streamlit](https://streamlit.io/) |
| LLM (jawaban & transkripsi suara) | [Groq API](https://groq.com/) (model `openai/gpt-oss-120b` + Whisper `whisper-large-v3`) |
| Pencarian web (grounding) | [Tavily API](https://tavily.com/) |
| Peta & geocoding | [Folium](https://python-visualization.github.io/folium/) + [Geopy](https://geopy.readthedocs.io/) (Nominatim/OpenStreetMap) |
| Cuaca | [Open-Meteo](https://open-meteo.com/) |

## 🚀 Menjalankan secara lokal

1. **Clone repo & masuk ke folder proyek**
   ```bash
   git clone https://github.com/Muhammadrifkiyahyaaa/beta-ai-tapin.git
   cd beta-ai-tapin
   ```

2. **Buat virtual environment & install dependency**
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   # source venv/bin/activate # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Siapkan file `.env`** di root folder, isi dengan API key berikut:
   ```env
   GROQ_API_KEY=isi_dengan_groq_api_key_kamu
   TAVILY_API_KEY=isi_dengan_tavily_api_key_kamu
   ```

4. **Jalankan aplikasi**
   ```bash
   streamlit run app.py
   ```
   Aplikasi akan otomatis terbuka di `http://localhost:8501`.

## 📁 Struktur Proyek

```
beta-ai-tapin/
├── app.py                       # Entry point Streamlit — UI, layout, dialog fitur
├── services/
│   ├── search_client.py         # Logika inti AI: search grounding, filter relevansi,
│   │                               deteksi bahasa, geocoding, transkripsi suara
│   └── weather_client.py        # Ambil & format data cuaca (Open-Meteo)
├── data/
│   └── scope_filter.py          # Daftar kata kunci topik/lokasi/blokir untuk
│                                   memastikan pertanyaan relevan dengan Tapin
├── prompts/
│   └── system_prompt.py         # System prompt untuk AI (Groq)
├── static/
│   └── style.css                # Styling custom untuk komponen UI
├── assets/
│   └── logo.png                 # Logo BETA AI
├── .streamlit/
│   └── config.toml              # Konfigurasi tema/tampilan Streamlit
├── .devcontainer/
│   └── devcontainer.json        # Konfigurasi dev container (opsional, GitHub Codespaces)
├── requirements.txt
├── .gitignore
└── .env                         # API key (tidak di-commit ke Git)
```

## ⚠️ Catatan

Chatbot ini menggunakan data hasil pencarian internet (bukan data resmi dari Disbudpar Tapin), jadi informasi yang diberikan bisa saja tidak lengkap atau perlu dikonfirmasi ulang di lapangan — terutama untuk estimasi biaya dan jam operasional tempat wisata.

## 👤 Developer

Muhammad Rifki Yahya — Duta GenRe Inovator Putra Tapin 2025
