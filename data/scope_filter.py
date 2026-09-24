# Kata kunci topik yang diizinkan (pariwisata & sejenisnya)
TOPIC_KEYWORDS = [
    "wisata", "destinasi", "pariwisata", "umkm", "produk lokal", "usaha",
    "tradisi", "adat", "budaya", "kuliner", "makanan khas", "event", "festival",
    "kerajinan", "oleh-oleh", "sejarah", "desa wisata", "air terjun",
    "sungai", "pasar", "museum", "masjid", "candi",
    # Sampah & kebersihan wisata (dikaitkan ke wisata/UMKM, bukan topik
    # lingkungan umum yang berdiri sendiri)
    "sampah", "bank sampah", "daur ulang", "kompos", "kelola sampah",
    "pengelolaan sampah", "kebersihan wisata", "kebersihan destinasi",
    "buang sampah", "pilah sampah",
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


# Kata kunci yang menandakan pertanyaan user seputar rencana jalan-jalan
# atau wisata outdoor/alam -> dipakai untuk memicu munculnya info cuaca
# otomatis di jawaban (lihat app.py).
NATURE_ITINERARY_KEYWORDS = [
    "itinerary", "rencana", "jalan-jalan", "jalan2", "trip", "liburan",
    "mau ke", "rencana ke", "wisata alam", "outdoor", "hiking", "trekking",
    "camping", "berkemah", "air terjun", "curug", "sungai", "pemandian",
    "bukit", "gunung", "danau", "pantai", "kapan waktu terbaik",
    "cocok kapan", "musim",
]


def mentions_nature_or_itinerary(text: str) -> bool:
    """
    Cek apakah teks pertanyaan menyinggung rencana perjalanan atau wisata
    alam/outdoor, di mana info cuaca terkini akan relevan untuk ditampilkan.
    """
    t = (text or "").lower()
    return any(k in t for k in NATURE_ITINERARY_KEYWORDS)


# Kata kunci yang memicu munculnya kartu pengingat "Jaga Kebersihan" di
# jawaban -> ditampilkan saat user tanya soal wisata alam/itinerary/sampah,
# supaya pesan #JagaKebersihan selalu nempel di konteks yang relevan.
CLEANLINESS_REMINDER_KEYWORDS = NATURE_ITINERARY_KEYWORDS + [
    "sampah", "bank sampah", "daur ulang", "kompos", "kelola sampah",
    "pengelolaan sampah", "kebersihan wisata", "kebersihan destinasi",
    "buang sampah", "pilah sampah", "wisata alam",
]


def mentions_cleanliness_topic(text: str) -> bool:
    """
    Cek apakah pertanyaan user relevan untuk menampilkan kartu pengingat
    kebersihan/pengelolaan sampah (dipakai di app.py).
    """
    t = (text or "").lower()
    return any(k in t for k in CLEANLINESS_REMINDER_KEYWORDS)


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