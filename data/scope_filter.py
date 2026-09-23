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

# Kata kunci yang SELALU dianggap di luar topik, walaupun kata "Tapin" ikut
# disebutkan di pertanyaan. Menang di atas LOCATION_KEYWORDS/TOPIC_KEYWORDS.
BLOCKED_KEYWORDS = [
    # Pemerintahan & politik (bukan wisata/budaya)
    "bupati", "wabup", "wakil bupati", "gubernur", "wakil gubernur",
    "presiden", "wakil presiden", "wapres", "menteri", "dprd", "dpr",
    "mpr", "pemilu", "pilkada", "pilpres", "partai", "capres", "cawapres",
    "caleg", "anggota dewan", "kapolres", "polres", "kapolsek", "dandim",
    "kodim", "tni", "polri", "kepala daerah", "pns", "asn", "apbd",
    # Cafe / coffee shop modern (di luar cakupan "kuliner khas" resmi)
    "cafe", "kafe", "coffee shop", "coffeeshop",
]


def is_in_scope(question: str) -> bool:
    """
    Cek apakah pertanyaan user relevan untuk diproses.
    Pertanyaan ditolak lebih dulu kalau menyinggung topik yang memang
    di luar cakupan (politik/pemerintahan, cafe/coffee shop), walaupun
    kata "Tapin" ikut disebutkan.
    Selain itu, dianggap relevan kalau menyebut lokasi Tapin secara
    eksplisit, ATAU menyebut topik wisata/UMKM/tradisi (diasumsikan user
    masih membicarakan konteks Tapin, akan diperjelas lagi lewat pencarian).
    """
    q = question.lower()

    is_blocked = any(k in q for k in BLOCKED_KEYWORDS)
    if is_blocked:
        return False

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