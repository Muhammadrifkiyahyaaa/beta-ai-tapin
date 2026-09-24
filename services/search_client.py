import json
import re
import os
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic

from data.scope_filter import mentions_tapin
from prompts.system_prompt import SYSTEM_PROMPT, GENERATOR_SYSTEM_PROMPT

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY tidak ditemukan. Pastikan sudah diisi di file .env")
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY tidak ditemukan. Pastikan sudah diisi di file .env")

groq_client = Groq(api_key=GROQ_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

MODEL_NAME = "openai/gpt-oss-120b"

# Titik tengah Kabupaten Tapin (sekitar Rantau), dipakai sebagai fallback
# posisi peta kalau tidak ada tempat yang berhasil di-geocode.
TAPIN_CENTER = (-2.8397, 115.0186)

# Radius maksimum (km) dari titik tengah Tapin. Hasil geocoding yang
# jatuhnya lebih jauh dari ini dianggap SALAH TEMPAT (misalnya Nominatim
# kebetulan mencocokkan nama yang sama di kabupaten/provinsi lain) dan
# akan dibuang, bukan ditampilkan di peta. Kabupaten Tapin sendiri kira-kira
# berdiameter 60-70km, jadi 45km dari titik tengah sudah cukup longgar
# untuk mencakup seluruh wilayahnya plus sedikit area perbatasan.
MAX_DISTANCE_FROM_TAPIN_KM = 45

_geolocator = Nominatim(user_agent="beta-ai-tapin-app")
_geocode_raw = RateLimiter(_geolocator.geocode, min_delay_seconds=1, max_retries=1)

# Kata-kata umum (stopwords) yang dipakai untuk menebak bahasa pertanyaan user
# secara ringan, tanpa perlu library deteksi bahasa tambahan. Cukup akurat
# untuk kalimat tanya pendek khas turis, mis. "What are the best waterfalls
# in Tapin?" vs "Wisata air terjun apa saja di Tapin?".
_ID_STOPWORDS = {
    "apa", "yang", "dimana", "di", "mana", "kapan", "bagaimana", "gimana",
    "saya", "kamu", "anda", "kita", "ke", "dan", "atau", "untuk", "dengan",
    "adalah", "tidak", "ini", "itu", "ada", "saja", "bisa", "tolong",
    "mohon", "berapa", "kenapa", "mengapa", "siapa", "nya", "ya", "dong",
    "aja", "gak", "nggak", "enggak", "kah",
}
_EN_STOPWORDS = {
    "what", "where", "when", "how", "why", "who", "is", "are", "the", "a",
    "an", "and", "or", "for", "with", "not", "this", "that", "these",
    "those", "can", "could", "you", "your", "please", "i", "me", "my",
    "do", "does", "there", "any", "recommend", "recommendation", "best",
    "tell", "about", "to", "in", "of", "want", "like", "visit", "trip",
}


def detect_language(text: str) -> str:
    """
    Tebak bahasa pertanyaan user: "en" (Inggris) atau "id" (Indonesia,
    dipakai juga sebagai default kalau ragu/tidak jelas). Dihitung dari
    jumlah stopword bahasa Inggris vs Indonesia yang muncul di teksnya.
    """
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    if not words:
        return "id"
    id_hits = sum(1 for w in words if w in _ID_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    if en_hits > id_hits and en_hits > 0:
        return "en"
    return "id"


# Kata-kata generik yang sering ditempel di depan nama tempat wisata lokal
# ("Pemandian Sirang Pitu" -> intinya "Sirang Pitu"), tapi biasanya TIDAK
# terdaftar sebagai bagian dari nama resmi di OpenStreetMap. Diurutkan dari
# frasa 2 kata dulu supaya "air terjun" tidak kepotong jadi "terjun" doang.
_GENERIC_PLACE_PREFIXES = [
    "objek wisata", "obyek wisata", "tempat wisata", "wisata alam",
    "air terjun", "danau", "bukit", "gunung", "goa", "gua", "pantai",
    "taman", "kolam", "curug", "pemandian", "wisata", "sungai", "kampung",
    "desa", "kebun", "hutan", "pulau", "tebing", "situs", "makam", "kawasan",
]


def _strip_generic_prefix(text: str) -> str:
    """Buang 1 lapis kata generik di depan teks, kalau ada. 'Pemandian Sirang
    Pitu' -> 'Sirang Pitu'. Kalau tidak ada prefix yang cocok, balikin apa
    adanya."""
    lower = text.lower()
    for prefix in _GENERIC_PLACE_PREFIXES:
        if lower.startswith(prefix + " "):
            return text[len(prefix):].strip()
    return text


def _build_query_variants(name: str) -> list:
    """
    Susun daftar variasi nama tempat untuk dicoba geocode, dari yang paling
    spesifik ke yang paling umum. Ide dasarnya: nama spesifik seperti
    "Pemandian Sirang Pitu" sering tidak terdaftar di OpenStreetMap, tapi
    nama desa/kecamatan yang menyertainya ("Desa Buniin Jaya") atau nama inti
    tempatnya ("Sirang Pitu", tanpa kata generik "Pemandian") kemungkinan
    besar ada.
    """
    name = name.strip()
    parts = [p.strip() for p in name.split(",") if p.strip()]
    first_part = parts[0] if parts else name
    village_part = parts[-1] if len(parts) > 1 else None
    core = _strip_generic_prefix(first_part)

    variants = []

    def add(v):
        v = (v or "").strip(" ,")
        if v and v not in variants:
            variants.append(v)

    # 1. Nama lengkap apa adanya (paling spesifik)
    add(name)
    # 2. Kalau ada bagian desa/kecamatan terpisah, coba itu saja
    add(village_part)
    # 3. Nama inti (tanpa kata generik) + bagian desa/kecamatan
    if core != first_part:
        add(f"{core}, {village_part}" if village_part else core)
    # 4. Nama inti sendirian (paling umum, upaya terakhir)
    add(core)

    return variants


def geocode_place(name: str):
    """
    Cari koordinat (lat, lon) sebuah nama tempat. Dicoba beberapa variasi
    nama (dari paling spesifik ke paling umum, lihat `_build_query_variants`)
    dikombinasikan dengan bias wilayah dari paling sempit (Kabupaten Tapin)
    ke paling longgar (Kalimantan Selatan saja), karena banyak nama
    tempat/dusun kecil tidak terdaftar persis dengan nama lengkapnya di
    OpenStreetMap. Balikin None kalau semua percobaan gagal ATAU kalau
    satu-satunya hasil yang ketemu ternyata di luar wilayah Tapin (lihat
    MAX_DISTANCE_FROM_TAPIN_KM) - lebih baik tidak muncul di peta sama
    sekali daripada muncul tapi lokasinya salah/nyasar ke daerah lain.
    """
    tried = []
    for variant in _build_query_variants(name):
        for suffix in (
            ", Kabupaten Tapin, Kalimantan Selatan, Indonesia",
            ", Kalimantan Selatan, Indonesia",
        ):
            query = f"{variant}{suffix}"
            if query in tried:
                continue
            tried.append(query)
            try:
                location = _geocode_raw(query)
                if not location:
                    continue

                distance_km = geodesic(
                    TAPIN_CENTER, (location.latitude, location.longitude)
                ).km
                if distance_km > MAX_DISTANCE_FROM_TAPIN_KM:
                    print(
                        f"[BETA AI] Geocoding '{name}' -> '{query}' ditolak: "
                        f"{distance_km:.1f}km dari pusat Tapin (di luar wilayah)."
                    )
                    continue

                return {"name": name, "lat": location.latitude, "lon": location.longitude}
            except Exception:
                continue

    print(f"[BETA AI] Geocoding gagal untuk tempat: '{name}' (dicoba: {tried})")
    return None


def geocode_places(names: list, max_places: int = 5):
    """Geocode beberapa nama tempat sekaligus, buang yang gagal ditemukan."""
    places = []
    for name in (names or [])[:max_places]:
        name = (name or "").strip()
        if not name:
            continue
        geocoded = geocode_place(name)
        if geocoded:
            places.append(geocoded)
    return places


def _simplify_query(text: str) -> str:
    """
    Sederhanakan teks pertanyaan untuk percobaan pencarian ke-2 (retry),
    dengan membuang tanda baca dan kata-kata subjektif/pengisi (mis. "unik",
    "khas", "menarik") yang kadang membuat hasil pencarian Tavily melenceng
    dibanding kalau usernya ketik manual dengan kalimat yang lebih polos.
    """
    t = (text or "").strip()
    t = re.sub(r"[?!.,]", " ", t)
    filler_words = [
        "unik", "khas", "menarik", "seru", "keren", "terbaik", "paling",
        "apa saja", "apa aja", "gimana", "bagaimana",
    ]
    lowered = t.lower()
    for fw in filler_words:
        lowered = lowered.replace(fw, " ")
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered or t.strip()


# Kata-kata umum/generik yang TIDAK dipakai sebagai "kata kunci topik" saat
# mengecek relevansi hasil pencarian -> supaya yang tersisa cuma kata inti
# topiknya (mis. "umkm", "tradisi", "kuliner"), bukan kata lokasi/pengisi
# yang hampir selalu ada di semua hasil pencarian apa pun topiknya.
# Digabung dengan _ID_STOPWORDS & _EN_STOPWORDS supaya pertanyaan Inggris
# juga tidak salah anggap kata seperti "what/are/the" sebagai topik.
_RELEVANCE_STOPWORDS = _ID_STOPWORDS | _EN_STOPWORDS | {
    "kabupaten", "tapin", "kalimantan", "selatan", "apa", "saja", "aja",
    "yang", "di", "ke", "dan", "atau", "itu", "ini", "adalah", "untuk",
    "dari", "ada", "bagaimana", "gimana", "unik", "khas", "menarik",
    "terbaik", "paling", "seru", "keren", "gimana", "bagaimana", "coba",
    "tolong", "bisa", "dong", "gan", "mas",
}

# Terjemahan istilah topik Inggris -> Indonesia. Sumber data (Tavily hasil
# indeks web Kalsel) hampir semuanya berbahasa Indonesia, jadi kata topik
# bahasa Inggris seperti "culinary" nyaris tidak pernah match apapun -
# baik di query pencarian maupun di filter relevansi. Peta ini dipakai
# untuk menyisipkan padanan Indonesianya supaya pencarian & filter tetap
# jalan walau usernya bertanya dalam bahasa Inggris.
_EN_TO_ID_TOPIC_MAP = {
    "culinary": "kuliner", "cuisine": "kuliner", "food": "makanan khas",
    "dish": "makanan khas", "dishes": "makanan khas", "snack": "makanan khas",
    "specialty": "khas", "specialties": "khas",
    "tradition": "tradisi", "traditions": "tradisi",
    "custom": "adat", "customs": "adat", "culture": "budaya",
    "craft": "kerajinan", "crafts": "kerajinan", "handicraft": "kerajinan",
    "souvenir": "oleh-oleh", "souvenirs": "oleh-oleh",
    "waterfall": "air terjun", "waterfalls": "air terjun",
    "market": "pasar", "festival": "festival", "event": "event",
    "nature": "alam", "tourism": "wisata", "tourist": "wisata",
    "attraction": "wisata", "attractions": "wisata", "destination": "destinasi",
    "destinations": "destinasi", "history": "sejarah", "historic": "sejarah",
    "msme": "umkm", "sme": "umkm", "business": "usaha", "product": "produk",
    "products": "produk", "signature": "khas",
}


def _translate_en_topic_terms(text: str) -> str:
    """
    Cari kata-kata topik Inggris yang dikenal di `_EN_TO_ID_TOPIC_MAP` pada
    teks, lalu balikin padanan Indonesianya (dipisah spasi, boleh ada
    duplikat -> tidak masalah untuk keperluan query & keyword matching).
    Balikin string kosong kalau tidak ada satupun yang cocok.
    """
    words = re.findall(r"[a-zA-Z]+", (text or "").lower())
    translated = [_EN_TO_ID_TOPIC_MAP[w] for w in words if w in _EN_TO_ID_TOPIC_MAP]
    return " ".join(dict.fromkeys(translated))  # buang duplikat, jaga urutan


def _extract_relevance_keywords(text: str) -> list:
    """
    Ambil kata-kata inti topik dari pertanyaan (mis. "UMKM khas Kabupaten
    Tapin?" -> ["umkm"]), dengan membuang kata lokasi & kata pengisi umum.
    Dipakai untuk memastikan hasil pencarian yang lolos filter BENERAN
    membahas topiknya, bukan cuma kebetulan menyebut "Tapin". Kalau
    pertanyaannya Inggris, padanan Indonesianya (kalau dikenal) ikut
    ditambahkan sebagai kata kunci, karena sumber datanya berbahasa
    Indonesia.
    """
    words = re.findall(r"[a-zA-Z]+", (text or "").lower())
    keywords = [w for w in words if len(w) > 2 and w not in _RELEVANCE_STOPWORDS]
    translated = _translate_en_topic_terms(text)
    if translated:
        keywords.extend(translated.split())
    return keywords


def _is_topically_relevant(result_text: str, keywords: list) -> bool:
    """
    True kalau tidak ada kata kunci topik yang bisa diekstrak (jadi tidak
    bisa dicek, dianggap lolos), ATAU kalau minimal salah satu kata kunci
    topik itu memang muncul di teks hasil pencarian (judul+isi).
    """
    if not keywords:
        return True
    lowered = (result_text or "").lower()
    return any(kw in lowered for kw in keywords)


def _parse_ai_json(raw_text: str):
    """
    Parse balasan AI yang seharusnya berupa JSON murni (lihat system_prompt.py).
    Cukup toleran: kalau AI tetap membungkus dengan ```json ... ``` atau ada
    teks nyasar di luar objek JSON, tetap coba ambil blok {...} pertama.
    """
    text = (raw_text or "").strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return None


def transcribe_audio(audio_bytes: bytes, audio_format: str = "webm", language: str = "id"):
    """
    Ubah rekaman suara user jadi teks pakai Groq Whisper (whisper-large-v3),
    supaya bisa diproses persis seperti pertanyaan yang diketik biasa. Pakai
    API key Groq yang sama dengan yang dipakai untuk chat (tidak perlu
    layanan/API key tambahan).

    Balikin None kalau gagal (rekaman kosong, suara tidak jelas, error
    koneksi/API) supaya UI bisa kasih pesan yang ramah, bukan bikin
    aplikasi crash.
    """
    if not audio_bytes:
        return None
    try:
        transcription = groq_client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(f"rekaman.{audio_format}", audio_bytes),
            language=language,
        )
        text = (transcription.text or "").strip()
        return text or None
    except Exception as e:
        print(f"[BETA AI] Gagal transkripsi suara: {e}")
        return None


def search_web(query: str, max_results: int = 6, include_images: bool = False, search_depth: str = "basic"):
    # Bersihkan tanda tanya/seru dari query SEBELUM dikirim ke Tavily.
    # Tanda baca seperti "?" ternyata bisa mengubah cara mesin pencari
    # me-ranking hasilnya, sehingga pertanyaan yang identik isinya (cuma beda
    # ada/tidaknya "?", misal dari tombol contoh pertanyaan) bisa memberi
    # hasil pencarian yang berbeda dibanding kalau user ketik manual tanpa
    # tanda tanya. Teks pertanyaan ASLI (dengan "?") tetap dipakai apa adanya
    # untuk prompt ke AI, ini cuma membersihkan query pencariannya saja.
    clean_query = re.sub(r"[?!]", " ", query)
    clean_query = re.sub(r"\s+", " ", clean_query).strip()

    full_query = f"{clean_query} Kabupaten Tapin Kalimantan Selatan"
    response = tavily_client.search(
        query=full_query,
        max_results=max_results,
        search_depth=search_depth,
        include_images=include_images,
        include_image_descriptions=include_images,
        # Domain-domain direktori/listing generik yang sering nongol untuk
        # SEMUA jenis pertanyaan yang menyebut "Kabupaten Tapin" (misal
        # direktori sekolah), padahal isinya tidak relevan sama sekali
        # dengan topik yang ditanyakan (wisata/UMKM/tradisi/dst). Domain ini
        # cuma "numpang lolos" filter lokasi karena rajin menyebut nama
        # kabupaten & kecamatan, jadi diblokir langsung dari pencarian.
        exclude_domains=["daftarsekolah.net"],
    )
    results = response.get("results", [])
    images = response.get("images", []) if include_images else []
    return results, images


def ask_beta_ai(question: str, system_prompt: str):
    lang = detect_language(question)
    topic_keywords = _extract_relevance_keywords(question)
    # Untuk pertanyaan Inggris, sisipkan padanan topik Indonesianya ke query
    # yang dikirim ke Tavily juga -- bukan cuma ke filter relevansi -- karena
    # sumber datanya berbahasa Indonesia dan istilah seperti "culinary" nyaris
    # tidak pernah match apapun kalau dikirim apa adanya.
    search_query = question
    if lang == "en":
        id_terms = _translate_en_topic_terms(question)
        if id_terms:
            search_query = f"{question} {id_terms}"

    def _filter(results):
        return [
            r for r in results
            if mentions_tapin(r.get("title", "") + " " + r.get("content", ""))
            and _is_topically_relevant(
                r.get("title", "") + " " + r.get("content", ""), topic_keywords
            )
        ]

    raw_results, raw_images = search_web(search_query, include_images=True)
    filtered_results = _filter(raw_results)

    print(
        f"[BETA AI][DEBUG] Pertanyaan: {question!r} | Kata kunci topik: {topic_keywords} | "
        f"Hasil mentah percobaan 1: {len(raw_results)} "
        f"(judul: {[r.get('title') for r in raw_results]}) | "
        f"Lolos filter Tapin+topik: {len(filtered_results)}"
    )

    if not filtered_results:
        # Percobaan pertama (pencarian "basic") tidak menghasilkan sumber yang
        # lolos filter Tapin -> coba lagi sekali dengan pencarian yang lebih
        # dalam ("advanced") & hasil lebih banyak, sebelum benar-benar
        # menyerah. Ini mengatasi kasus di mana kalimat pertanyaan (misal versi
        # contoh pertanyaan di dashboard vs ketikan manual user) menghasilkan
        # hasil pencarian yang berbeda-beda karena sifat pencarian web
        # real-time yang tidak selalu konsisten.
        retry_query = _simplify_query(search_query)
        raw_results, raw_images = search_web(
            retry_query, max_results=10, include_images=True,
            search_depth="advanced",
        )
        filtered_results = _filter(raw_results)
        print(
            f"[BETA AI][DEBUG] Retry query: {retry_query!r} | "
            f"Hasil mentah percobaan 2: {len(raw_results)} "
            f"(judul: {[r.get('title') for r in raw_results]}) | "
            f"Lolos filter Tapin+topik: {len(filtered_results)}"
        )

    if not filtered_results:
        if lang == "en":
            return (
                "Sorry, I couldn't find information specifically about Kabupaten Tapin "
                "for this question. Try asking about a more specific place or topic in "
                "Tapin.",
                [],
                [],
                [],
            )
        return (
            "Maaf, saya tidak menemukan informasi yang spesifik membahas Kabupaten Tapin "
            "untuk pertanyaan ini. Coba tanyakan dengan menyebut nama tempat/topik yang "
            "lebih spesifik di Tapin ya.",
            [],
            [],
            [],
        )

    context_text = "\n\n".join(
        f"Sumber: {r['title']}\nURL: {r['url']}\nIsi: {r['content']}"
        for r in filtered_results
    )

    language_note = (
        "Bahasa pertanyaan user terdeteksi: Inggris (English). WAJIB jawab dalam "
        "bahasa Inggris."
        if lang == "en"
        else "Bahasa pertanyaan user terdeteksi: Indonesia. Jawab dalam bahasa Indonesia."
    )

    user_message = (
        f"Pertanyaan user: {question}\n\n"
        f"{language_note}\n\n"
        f"Berikut hasil pencarian internet yang SUDAH DIPASTIKAN membahas Kabupaten Tapin:\n\n"
        f"{context_text}\n\n"
        f"Jawab pertanyaan user HANYA berdasarkan informasi di atas. "
        f"Kalau ada bagian yang ternyata membahas daerah lain (bukan Tapin), abaikan bagian itu."
    )

    completion = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw_answer = completion.choices[0].message.content or ""
    parsed = _parse_ai_json(raw_answer)

    print(
        f"[BETA AI][DEBUG] Jumlah sumber dikirim ke AI: {len(filtered_results)} | "
        f"Balasan mentah AI: {raw_answer[:500]!r}"
    )

    if parsed is None:
        # Balasan AI tidak berhasil di-parse sebagai JSON -> demi keamanan,
        # anggap out of scope tapi tetap tampilkan teks mentahnya ke user.
        fallback = (
            "Sorry, something went wrong while processing the answer."
            if lang == "en"
            else "Maaf, terjadi kesalahan saat memproses jawaban."
        )
        return (raw_answer.strip() or fallback, [], [], [])

    scope = str(parsed.get("scope", "")).strip().upper()
    answer_text = str(parsed.get("answer", "")).strip()
    place_names = parsed.get("places", []) if isinstance(parsed.get("places"), list) else []

    if scope != "IN_SCOPE":
        fallback = (
            "Sorry, this question is outside what I can help with."
            if lang == "en"
            else "Maaf, pertanyaan ini di luar topik yang bisa saya bantu."
        )
        return (answer_text or fallback, [], [], [])

    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]
    images = raw_images[:3]
    print(f"[BETA AI] Nama tempat dari AI: {place_names}")
    places = geocode_places(place_names)
    print(f"[BETA AI] Berhasil dipetakan: {[p['name'] for p in places]}")

    return answer_text, sources, images, places


def generate_itinerary(days: int, interests: list):
    interest_text = ", ".join(interests) if interests else "wisata umum"
    raw_results, _ = search_web(f"{interest_text} rekomendasi tempat", max_results=8)

    filtered_results = [
        r for r in raw_results
        if mentions_tapin(r.get("title", "") + " " + r.get("content", ""))
    ]

    if not filtered_results:
        return None, []

    context_text = "\n\n".join(
        f"Sumber: {r['title']}\nURL: {r['url']}\nIsi: {r['content']}"
        for r in filtered_results
    )

    prompt = (
        f"Buatkan rencana perjalanan (itinerary) wisata ke Kabupaten Tapin selama {days} hari, "
        f"dengan fokus minat: {interest_text}.\n\n"
        f"Berikut referensi tempat/topik yang SUDAH DIPASTIKAN tentang Tapin:\n\n"
        f"{context_text}\n\n"
        f"Susun rencana per hari (## Hari 1, ## Hari 2, dst dalam format markdown), tiap hari "
        f"dibagi jadi Pagi / Siang / Sore, sebutkan nama tempat atau aktivitas spesifik yang ADA "
        f"di referensi di atas. JANGAN mengarang tempat yang tidak disebutkan di referensi. Kalau "
        f"referensinya terbatas, buat rencana sesederhana mungkin sesuai yang tersedia saja."
    )

    completion = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )

    itinerary_text = completion.choices[0].message.content
    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]

    return itinerary_text, sources


def generate_budget_estimate(people: int, days: int, tier: str):
    raw_results, _ = search_web(
        "estimasi biaya transportasi lokal makan penginapan wisata", max_results=8
    )

    filtered_results = [
        r for r in raw_results
        if mentions_tapin(r.get("title", "") + " " + r.get("content", ""))
    ]

    context_text = (
        "\n\n".join(
            f"Sumber: {r['title']}\nURL: {r['url']}\nIsi: {r['content']}"
            for r in filtered_results
        )
        if filtered_results
        else "Tidak ditemukan referensi harga spesifik tentang Tapin."
    )

    prompt = (
        f"Buatkan estimasi kasar biaya kunjungan wisata ke Kabupaten Tapin untuk "
        f"{people} orang selama {days} hari, dengan kelas budget: {tier}.\n\n"
        f"Berikut referensi yang tersedia (boleh terbatas):\n\n{context_text}\n\n"
        f"Susun estimasi dalam format markdown berupa tabel dengan kolom: Kategori, "
        f"Perkiraan Biaya (Rp), Catatan. Kategori yang wajib dibahas: Transportasi lokal, "
        f"Makan, Penginapan (kalau relevan), Oleh-oleh/UMKM. Di akhir, beri baris 'Total "
        f"Estimasi' dengan rentang angka kasar (misal Rp500.000 - Rp800.000). WAJIB tutup "
        f"jawaban dengan kalimat: 'Catatan: Ini estimasi kasar berdasarkan referensi umum, "
        f"bukan harga resmi/tetap. Harga aktual bisa berbeda, mohon konfirmasi ulang di "
        f"lapangan.' Jangan mengarang angka yang sangat spesifik seolah-olah pasti akurat, "
        f"gunakan rentang wajar."
    )

    completion = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    estimate_text = completion.choices[0].message.content
    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]

    return estimate_text, sources


def generate_quiz_recommendation(answers: dict):
    profile_text = ", ".join(f"{k}: {v}" for k, v in answers.items())
    raw_results, _ = search_web(
        f"rekomendasi tempat wisata sesuai {answers.get('gaya', '')}", max_results=8
    )

    filtered_results = [
        r for r in raw_results
        if mentions_tapin(r.get("title", "") + " " + r.get("content", ""))
    ]

    context_text = (
        "\n\n".join(
            f"Sumber: {r['title']}\nURL: {r['url']}\nIsi: {r['content']}"
            for r in filtered_results
        )
        if filtered_results
        else "Tidak ditemukan referensi spesifik, gunakan jenis wisata secara umum saja."
    )

    prompt = (
        f"User baru saja mengisi kuis dengan profil berikut: {profile_text}.\n\n"
        f"Berikut referensi tempat wisata yang tersedia tentang Kabupaten Tapin:\n\n"
        f"{context_text}\n\n"
        f"Buatkan rekomendasi personal (format markdown) dengan struktur:\n"
        f"1. Satu kalimat pembuka yang menyimpulkan 'tipe wisatawan' user berdasarkan "
        f"profilnya (kasih semacam julukan singkat, misal 'Petualang Santai' atau "
        f"'Pemburu Kuliner').\n"
        f"2. 2-3 rekomendasi tempat/aktivitas SPESIFIK dari referensi di atas yang paling "
        f"cocok dengan profilnya, masing-masing dengan alasan singkat kenapa cocok.\n"
        f"JANGAN mengarang tempat yang tidak ada di referensi. Kalau referensi terbatas, "
        f"beri rekomendasi jenis wisata secara umum saja tanpa nama tempat spesifik."
    )

    completion = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    recommendation_text = completion.choices[0].message.content
    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]

    return recommendation_text, sources