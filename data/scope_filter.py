# Kata kunci topik yang diizinkan (pariwisata & sejenisnya)
TOPIC_KEYWORDS = [
    "wisata", "destinasi", "pariwisata", "umkm", "produk lokal", "usaha",
    "tradisi", "adat", "budaya", "kuliner", "makanan khas", "event", "festival",
    "kerajinan", "oleh-oleh", "sejarah", "desa wisata", "air terjun",
    "sungai", "pasar", "museum", "masjid", "candi",
]

# Kata kunci lokasi yang menandakan konteksnya benar-benar Kabupaten Tapin
LOCATION_KEYWORDS = [
    "tapin", "bekantan tapin", "rantau", "candi laras", "bungur", "hatungun",
    "binuang", "piani", "lokpaikat", "salam babaris", "tapin utara",
    "tapin selatan", "tapin tengah",
]


def is_in_scope(question: str) -> bool:
    """
    Cek apakah pertanyaan user relevan untuk diproses.
    Dianggap relevan kalau menyebut lokasi Tapin secara eksplisit,
    ATAU menyebut topik wisata/UMKM/tradisi (diasumsikan user masih
    membicarakan konteks Tapin, akan diperjelas lagi lewat pencarian).
    """
    q = question.lower()
    has_location = any(k in q for k in LOCATION_KEYWORDS)
    has_topic = any(k in q for k in TOPIC_KEYWORDS)
    return has_location or has_topic


def mentions_tapin(text: str) -> bool:
    """
    Cek apakah suatu teks (misal hasil pencarian dari internet) benar-benar
    menyinggung Kabupaten Tapin secara spesifik — bukan cuma Kalimantan
    Selatan secara umum. Dipakai untuk MENYARING hasil pencarian Tavily
    sebelum dikirim ke AI, supaya jawaban tidak melebar ke daerah lain.
    """
    text_lower = text.lower()
    return any(k in text_lower for k in LOCATION_KEYWORDS)