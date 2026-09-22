import os
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv

from data.scope_filter import mentions_tapin
from prompts.system_prompt import SYSTEM_PROMPT

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


def search_web(query: str, max_results: int = 6, include_images: bool = False):
    full_query = f"{query} Kabupaten Tapin Kalimantan Selatan"
    response = tavily_client.search(
        query=full_query,
        max_results=max_results,
        search_depth="basic",
        include_images=include_images,
        include_image_descriptions=include_images,
    )
    results = response.get("results", [])
    images = response.get("images", []) if include_images else []
    return results, images


def ask_beta_ai(question: str, system_prompt: str):
    raw_results, raw_images = search_web(question, include_images=True)

    filtered_results = [
        r for r in raw_results
        if mentions_tapin(r.get("title", "") + " " + r.get("content", ""))
    ]

    if not filtered_results:
        return (
            "Maaf, saya tidak menemukan informasi yang spesifik membahas Kabupaten Tapin "
            "untuk pertanyaan ini. Coba tanyakan dengan menyebut nama tempat/topik yang "
            "lebih spesifik di Tapin ya.",
            [],
            [],
        )

    context_text = "\n\n".join(
        f"Sumber: {r['title']}\nURL: {r['url']}\nIsi: {r['content']}"
        for r in filtered_results
    )

    user_message = (
        f"Pertanyaan user: {question}\n\n"
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
    )

    answer_text = completion.choices[0].message.content
    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]
    images = raw_images[:3]

    return answer_text, sources, images


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
            {"role": "system", "content": SYSTEM_PROMPT},
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
            {"role": "system", "content": SYSTEM_PROMPT},
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    recommendation_text = completion.choices[0].message.content
    sources = [{"title": r["title"], "url": r["url"]} for r in filtered_results]

    return recommendation_text, sources