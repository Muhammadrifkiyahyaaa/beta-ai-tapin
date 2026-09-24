import base64
import html as html_lib
from pathlib import Path

import folium
import streamlit as st

from data.scope_filter import is_in_scope, mentions_nature_or_itinerary, mentions_cleanliness_topic
from prompts.system_prompt import SYSTEM_PROMPT
from services.search_client import (
    ask_beta_ai,
    generate_itinerary,
    generate_budget_estimate,
    generate_quiz_recommendation,
    transcribe_audio,
)
from services.weather_client import get_tapin_weather

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
CSS_PATH = Path(__file__).parent / "static" / "style.css"
logo_exists = LOGO_PATH.exists()

st.set_page_config(
    page_title="BETA AI - Bekantan Tapin AI",
    page_icon=str(LOGO_PATH) if logo_exists else None,
    layout="centered",
)

import streamlit.components.v1 as components

components.html(
    """
    <script>
    (function() {
        var meta = document.createElement('meta');
        meta.name = 'google-site-verification';
        meta.content = '5grDPUfiynH0KmDVpiRcS4l6zU9oAHQnbP_UvQ4zLcA';
        window.parent.document.head.appendChild(meta);
    })();
    </script>
    """,
    height=0,
)

def load_css(path: Path):
    if path.exists():
        st.markdown(f"<style>{path.read_text()}</style>", unsafe_allow_html=True)


def get_logo_base64():
    if logo_exists:
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return None


logo_b64 = get_logo_base64()


def render_copy_button(answer_text, key):
    escaped = html_lib.escape(answer_text)
    copy_html = f"""
    <div style="font-family: sans-serif;">
        <div id="answer-text-{key}" style="display:none; white-space:pre-wrap;">{escaped}</div>
        <span
            class="copy-link"
            onclick="navigator.clipboard.writeText(document.getElementById('answer-text-{key}').innerText);
                     this.innerText='Tersalin';
                     setTimeout(() => {{ this.innerText='Salin jawaban'; }}, 1500);">
            Salin jawaban
        </span>
    </div>
    """
    st.markdown(copy_html, unsafe_allow_html=True)


def render_images(images, max_images=3):
    if not images:
        return
    cols = st.columns(min(len(images), max_images))
    for i, img in enumerate(images[:max_images]):
        with cols[i]:
            st.image(img.get("url"), caption=img.get("description") or None, width="stretch")


def google_maps_url(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


@st.cache_data(ttl=600, show_spinner=False)
def _cached_tapin_weather():
    """Cache cuaca Tapin selama 10 menit supaya tidak nge-hit API cuaca
    berkali-kali tiap kali halaman/dialog re-render."""
    return get_tapin_weather()


def render_weather_card(weather):
    if not weather:
        st.markdown(
            '<div class="weather-unavailable">☁️ Info cuaca Tapin saat ini '
            "tidak tersedia. Cek BMKG atau aplikasi cuaca lain sebelum "
            "berangkat.</div>",
            unsafe_allow_html=True,
        )
        return

    warning_html = ""
    if weather.get("is_raining"):
        warning_html = (
            '<div class="weather-warning">⚠️ Sedang/berpotensi hujan — '
            "pertimbangkan bawa jas hujan atau siapkan rencana cadangan "
            "indoor.</div>"
        )

    desc = html_lib.escape(weather.get("description", ""))
    # Dibangun jadi satu baris utuh (tanpa newline/indentasi) supaya tidak
    # ada baris kosong di tengah HTML yang bisa membuat st.markdown salah
    # mengira ada blok baru (menyebabkan "</div>" muncul sebagai teks/kode
    # mentah alih-alih dirender sebagai tag penutup).
    card_html = (
        '<div class="weather-card">'
        f'<div class="weather-emoji">{weather.get("emoji", "🌡️")}</div>'
        "<div>"
        f'<div class="weather-temp">{weather.get("temperature")}°C &middot; {desc}</div>'
        f'<div class="weather-sub">Kelembapan {weather.get("humidity")}% &middot; Angin {weather.get("wind_speed")} km/j</div>'
        '<div class="weather-note">Cuaca terkini area Kabupaten Tapin &middot; sumber: Open-Meteo</div>'
        f"{warning_html}"
        "</div>"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


ECO_TIPS = [
    "Bawa pulang sampahmu sendiri kalau tidak ada tempat sampah di lokasi.",
    "Pilah sampah organik dan anorganik sebelum dibuang, ya.",
    "Sampah plastikmu bisa jadi rezeki UMKM daur ulang lokal kalau dipilah dari awal.",
    "Sisa makanan bisa diolah jadi kompos — tanya pengelola desa wisata soal bank sampahnya.",
]


def render_eco_reminder():
    import random

    tip = random.choice(ECO_TIPS)
    card_html = (
        '<div class="eco-card">'
        '<div class="eco-emoji">🌿</div>'
        "<div>"
        '<div class="eco-title">Yuk, Jaga Kebersihan Tempat Wisata</div>'
        f'<div class="eco-sub">{html_lib.escape(tip)}</div>'
        "</div>"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def render_map(places, key=None):
    if not places:
        return

    if len(places) == 1:
        center = [places[0]["lat"], places[0]["lon"]]
        zoom = 14
    else:
        center = [
            sum(p["lat"] for p in places) / len(places),
            sum(p["lon"] for p in places) / len(places),
        ]
        zoom = 11

    fmap = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
    for p in places:
        maps_url = google_maps_url(p["lat"], p["lon"])
        popup_html = (
            f'<b>{html_lib.escape(p["name"])}</b><br>'
            f'<a href="{maps_url}" target="_blank" rel="noopener">Buka di Google Maps</a>'
        )
        folium.Marker(
            location=[p["lat"], p["lon"]],
            tooltip=p["name"],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="orange", icon="map-pin", prefix="fa"),
        ).add_to(fmap)

    components.html(fmap._repr_html_(), height=370)

    cols = st.columns(min(len(places), 3))
    for i, p in enumerate(places):
        with cols[i % len(cols)]:
            st.link_button(
                f"📍 {p['name']}",
                google_maps_url(p["lat"], p["lon"]),
                width="stretch",
            )


@st.dialog("Hubungi Developer")
def show_contact_dialog():
    st.markdown(
        "Ada pertanyaan, masukan, atau kendala seputar BETA AI? "
        "Silakan hubungi developer langsung lewat WhatsApp di bawah ini."
    )

    st.markdown(
        """
        <div class="contact-card-static">
            <div class="contact-avatar">MR</div>
            <div>
                <div class="contact-name">Muhammad Rifki Yahya</div>
                <div class="contact-role">Developer BETA AI</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button(
        "💬  Chat di WhatsApp",
        "https://wa.me/6281314428332?text=Halo%20Rifki%2C%20saya%20ingin%20bertanya%20soal%20BETA%20AI",
        width="stretch",
    )

    if st.button("Tutup", width="stretch", key="close_contact_dialog"):
        st.rerun()


@st.dialog("Perencana Itinerary Wisata", width="large")
def show_itinerary_planner():
    st.markdown("Isi kebutuhan kunjunganmu, BETA AI akan susunkan rencana perjalanannya.")

    st.markdown("**Cuaca Tapin saat ini:**")
    render_weather_card(_cached_tapin_weather())
    render_eco_reminder()

    days = st.number_input("Berapa hari kunjungan?", min_value=1, max_value=5, value=2, step=1)
    interests = st.multiselect(
        "Minat wisata (boleh pilih lebih dari satu)",
        ["Wisata Alam", "Wisata Budaya", "Kuliner", "UMKM", "Tradisi & Event"],
        default=["Wisata Alam"],
    )

    if st.button("Buat Rencana", width="stretch", key="generate_itinerary_btn"):
        try:
            with st.spinner("Menyusun rencana perjalanan..."):
                itinerary_text, sources = generate_itinerary(days, interests)
        except Exception as e:
            st.error(f"Gagal terhubung ke server. Coba klik tombol sekali lagi. ({e})")
            itinerary_text, sources = None, []

        if itinerary_text is None:
            st.warning(
                "Maaf, belum menemukan referensi yang cukup spesifik tentang Tapin untuk "
                "minat ini. Coba pilih kombinasi minat yang lain, atau coba lagi sesaat lagi."
            )
        else:
            st.markdown(itinerary_text)
            if sources:
                with st.expander("Sumber"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']})")

    if st.button("Tutup", width="stretch", key="close_itinerary_dialog"):
        st.rerun()


@st.dialog("Kalkulator Estimasi Budget Wisata", width="large")
def show_budget_calculator():
    st.markdown("Isi detail kunjunganmu, BETA AI akan hitungkan perkiraan biayanya.")

    people = st.number_input("Jumlah orang", min_value=1, max_value=20, value=2, step=1)
    days = st.number_input("Jumlah hari", min_value=1, max_value=7, value=2, step=1, key="budget_days")
    tier = st.selectbox("Kelas budget", ["Hemat", "Menengah", "Nyaman"])

    if st.button("Hitung Estimasi", width="stretch", key="calc_budget_btn"):
        try:
            with st.spinner("Menghitung estimasi biaya..."):
                estimate_text, sources = generate_budget_estimate(people, days, tier)
        except Exception as e:
            st.error(f"Gagal terhubung ke server. Coba klik tombol sekali lagi. ({e})")
            estimate_text, sources = None, []

        if estimate_text:
            st.markdown(estimate_text)
            if sources:
                with st.expander("Sumber"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']})")

    if st.button("Tutup", width="stretch", key="close_budget_dialog"):
        st.rerun()


@st.dialog("Kuis: Wisata Tapin Cocoknya Kamu yang Mana?", width="large")
def show_travel_quiz():
    st.markdown("Jawab 4 pertanyaan singkat ini, BETA AI akan carikan rekomendasi yang paling cocok buatmu.")

    gaya = st.radio(
        "Kamu lebih suka wisata yang seperti apa?",
        ["Alam yang tenang", "Budaya & sejarah", "Kuliner & jajanan", "Rame-rame sama komunitas"],
    )
    budget = st.radio("Budget yang kamu siapkan?", ["Hemat", "Menengah", "Bebas"])
    teman = st.radio(
        "Kamu biasanya pergi...",
        ["Sendirian", "Bersama pasangan", "Bersama keluarga", "Rombongan teman"],
    )
    waktu = st.radio("Waktu yang kamu punya?", ["Setengah hari", "Seharian penuh", "Beberapa hari"])

    if st.button("Lihat Rekomendasi", width="stretch", key="quiz_submit_btn"):
        answers = {"gaya": gaya, "budget": budget, "teman": teman, "waktu": waktu}
        try:
            with st.spinner("Mencocokkan profil wisatamu..."):
                recommendation_text, sources = generate_quiz_recommendation(answers)
        except Exception as e:
            st.error(f"Gagal terhubung ke server. Coba klik tombol sekali lagi. ({e})")
            recommendation_text, sources = None, []

        if recommendation_text:
            st.markdown(recommendation_text)
            if sources:
                with st.expander("Sumber"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']})")

    if st.button("Tutup", width="stretch", key="close_quiz_dialog"):
        st.rerun()


load_css(CSS_PATH)

if st.button("Hubungi Developer", key="wa_dev_btn"):
    show_contact_dialog()

with st.sidebar:
    if logo_exists:
        st.image(str(LOGO_PATH), width=80)
    st.markdown("### BETA AI")
    st.caption("Bekantan Tapin AI")
    st.markdown(
        "Asisten seputar wisata, UMKM, tradisi, budaya, kuliner, dan event "
        "di Kabupaten Tapin, Kalimantan Selatan."
    )
    st.divider()
    if st.button("Perencana Itinerary Wisata", width="stretch", key="open_itinerary_btn"):
        show_itinerary_planner()
    if st.button("Kalkulator Estimasi Budget", width="stretch", key="open_budget_btn"):
        show_budget_calculator()
    if st.button("Kuis Wisata Cocokmu", width="stretch", key="open_quiz_btn"):
        show_travel_quiz()
    if st.button("Reset percakapan", width="stretch", key="reset_chat_btn"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

ASSISTANT_AVATAR = str(LOGO_PATH) if logo_exists else None

example_questions = [
    "Wisata alam apa saja di Tapin?",
    "UMKM khas Kabupaten Tapin?",
    "Tradisi unik masyarakat Tapin?",
    "Kuliner khas Tapin apa saja?",
]

clicked_example = None

if not st.session_state.messages:
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" class="greeting-logo">'
        if logo_b64
        else ""
    )
    st.markdown(
        f"""
        <div class="greeting-container">
            {logo_html}
            <div class="greeting-text">Halo, saya BETA AI</div>
            <div class="greeting-sub">Tanya apa saja seputar wisata, UMKM, tradisi, dan budaya Kabupaten Tapin</div>
            <div class="dev-credit">Dikembangkan oleh <strong>Muhammad Rifki Yahya</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    for i, eq in enumerate(example_questions):
        if cols[i % 2].button(eq, width="stretch", key=f"example_{i}"):
            clicked_example = eq
else:
    st.markdown("### BETA AI — Bekantan Tapin AI")

for idx, message in enumerate(st.session_state.messages):
    avatar = ASSISTANT_AVATAR if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_copy_button(message["content"], key=f"hist-{idx}")
            render_images(message.get("images", []))
            render_map(message.get("places", []), key=f"hist-map-{idx}")
        if message.get("sources"):
            with st.expander("Sumber"):
                for s in message["sources"]:
                    st.markdown(f"- [{s['title']}]({s['url']})")

if "voice_input_key" not in st.session_state:
    st.session_state.voice_input_key = 0
if "_last_voice_file_id" not in st.session_state:
    st.session_state._last_voice_file_id = None

with st.bottom:
    with st.container(key="composer_bar"):
        input_cols = st.columns([1, 6], gap="small")
        with input_cols[0]:
            audio_value = st.audio_input(
                "Tanya dengan suara",
                key=f"voice_input_{st.session_state.voice_input_key}",
                label_visibility="collapsed",
            )
        with input_cols[1]:
            typed_question = st.chat_input("Tanya sesuatu tentang Tapin...")

voice_question = None
if audio_value is not None and audio_value.file_id != st.session_state._last_voice_file_id:
    st.session_state._last_voice_file_id = audio_value.file_id
    with st.spinner("Mentranskrip suara..."):
        voice_question = transcribe_audio(audio_value.getvalue(), audio_format="wav")
    if not voice_question:
        st.warning(
            "Maaf, suaranya kurang jelas kedengarannya. Coba rekam ulang di "
            "tempat yang lebih tenang, atau ketik pertanyaannya langsung ya."
        )

st.markdown(
    '<div class="disclaimer-text">BETA AI mencari jawaban dari internet secara real-time. '
    "Mohon verifikasi info penting sebelum digunakan.</div>",
    unsafe_allow_html=True,
)

question = clicked_example or voice_question or typed_question

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        if not is_in_scope(question):
            answer = (
                "Maaf, BETA AI hanya bisa menjawab pertanyaan seputar wisata, UMKM, "
                "tradisi, budaya, kuliner, dan event di Kabupaten Tapin. "
                "Coba tanyakan hal lain seputar Tapin ya."
            )
            st.markdown(answer)
            render_copy_button(answer, key="live-scope")
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": [], "images": [], "places": []}
            )
        else:
            placeholder = st.empty()
            placeholder.markdown(
                '<div class="typing-indicator"><span></span><span></span><span></span></div>',
                unsafe_allow_html=True,
            )
            try:
                answer, sources, images, places = ask_beta_ai(question, SYSTEM_PROMPT)
            except Exception as e:
                answer = f"Maaf, terjadi kesalahan saat memproses pertanyaan: {e}"
                sources, images, places = [], [], []
            placeholder.empty()

            st.markdown(answer)
            render_copy_button(answer, key="live-answer")
            if mentions_nature_or_itinerary(question):
                render_weather_card(_cached_tapin_weather())
            if mentions_cleanliness_topic(question):
                render_eco_reminder()
            render_images(images)
            render_map(places, key="live-map")
            if sources:
                with st.expander("Sumber"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']})")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "images": images,
                    "places": places,
                }
            )

    if clicked_example or voice_question:
        if voice_question:
            st.session_state.voice_input_key += 1
        st.rerun()