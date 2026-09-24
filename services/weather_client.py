import requests

# Titik tengah Kabupaten Tapin (sekitar Rantau), sama dengan yang dipakai
# di search_client.py untuk fallback posisi peta.
TAPIN_LAT, TAPIN_LON = -2.8397, 115.0186

# Pemetaan WMO weather code (dipakai Open-Meteo) ke deskripsi Bahasa
# Indonesia + emoji. Referensi kode: https://open-meteo.com/en/docs
_WEATHER_CODE_MAP = {
    0: ("Cerah", "☀️"),
    1: ("Cerah berawan", "🌤️"),
    2: ("Berawan sebagian", "⛅"),
    3: ("Mendung", "☁️"),
    45: ("Berkabut", "🌫️"),
    48: ("Kabut beku", "🌫️"),
    51: ("Gerimis ringan", "🌦️"),
    53: ("Gerimis sedang", "🌦️"),
    55: ("Gerimis lebat", "🌧️"),
    56: ("Gerimis beku ringan", "🌧️"),
    57: ("Gerimis beku lebat", "🌧️"),
    61: ("Hujan ringan", "🌧️"),
    63: ("Hujan sedang", "🌧️"),
    65: ("Hujan lebat", "🌧️"),
    66: ("Hujan beku ringan", "🌧️"),
    67: ("Hujan beku lebat", "🌧️"),
    71: ("Salju ringan", "🌨️"),
    73: ("Salju sedang", "🌨️"),
    75: ("Salju lebat", "🌨️"),
    77: ("Butiran salju", "🌨️"),
    80: ("Hujan lokal ringan", "🌦️"),
    81: ("Hujan lokal sedang", "🌧️"),
    82: ("Hujan lokal lebat", "⛈️"),
    85: ("Salju lokal ringan", "🌨️"),
    86: ("Salju lokal lebat", "🌨️"),
    95: ("Badai petir", "⛈️"),
    96: ("Badai petir + hujan es ringan", "⛈️"),
    99: ("Badai petir + hujan es lebat", "⛈️"),
}


def _describe_weather_code(code):
    return _WEATHER_CODE_MAP.get(code, ("Kondisi tidak diketahui", "🌡️"))


def get_tapin_weather(timeout: int = 5):
    """
    Ambil cuaca terkini area Kabupaten Tapin dari Open-Meteo (API cuaca
    gratis, tanpa perlu API key). Dipakai sebagai info tambahan supaya
    rekomendasi itinerary/wisata alam lebih relevan (misal warning kalau
    lagi hujan sebelum saran ke air terjun/sungai).

    Balikin None kalau gagal ambil data (API down, tidak ada koneksi, dll)
    supaya fitur ini gagal dengan aman tanpa bikin seluruh aplikasi error.
    """
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": TAPIN_LAT,
                "longitude": TAPIN_LON,
                "current": (
                    "temperature_2m,relative_humidity_2m,precipitation,"
                    "weather_code,wind_speed_10m"
                ),
                "timezone": "Asia/Makassar",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})

        if not current:
            return None

        code = current.get("weather_code")
        description, emoji = _describe_weather_code(code)

        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "description": description,
            "emoji": emoji,
            "time": current.get("time"),
            "is_raining": (current.get("precipitation") or 0) > 0
            or (code is not None and code >= 51),
        }
    except Exception as e:
        print(f"[BETA AI] Gagal mengambil data cuaca Tapin: {e}")
        return None