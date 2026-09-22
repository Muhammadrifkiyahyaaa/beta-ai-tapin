import base64
import html as html_lib
from pathlib import Path

import streamlit as st

from data.scope_filter import is_in_scope
from prompts.system_prompt import SYSTEM_PROMPT
from services.search_client import (
    ask_beta_ai,
    generate_itinerary,
    generate_budget_estimate,
    generate_quiz_recommendation,
)

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
            st.image(img.get("url"), caption=img.get("description") or None, use_container_width=True)


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
        use_container_width=True,
    )

    if st.button("Tutup", use_container_width=True, key="close_contact_dialog"):
        st.rerun()


@st.dialog("Perencana Itinerary Wisata", width="large")
def show_itinerary_planner():
    st.markdown("Isi kebutuhan kunjunganmu, BETA AI akan susunkan rencana perjalanannya.")

    days = st.number_input("Berapa hari kunjungan?", min_value=1, max_value=5, value=2, step=1)
    interests = st.multiselect(
        "Minat wisata (boleh pilih lebih dari satu)",
        ["Wisata Alam", "Wisata Budaya", "Kuliner", "UMKM", "Tradisi & Event"],
        default=["Wisata Alam"],
    )

    if st.button("Buat Rencana", use_container_width=True, key="generate_itinerary_btn"):
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

    if st.button("Tutup", use_container_width=True, key="close_itinerary_dialog"):
        st.rerun()


@st.dialog("Kalkulator Estimasi Budget Wisata", width="large")
def show_budget_calculator():
    st.markdown("Isi detail kunjunganmu, BETA AI akan hitungkan perkiraan biayanya.")

    people = st.number_input("Jumlah orang", min_value=1, max_value=20, value=2, step=1)
    days = st.number_input("Jumlah hari", min_value=1, max_value=7, value=2, step=1, key="budget_days")
    tier = st.selectbox("Kelas budget", ["Hemat", "Menengah", "Nyaman"])

    if st.button("Hitung Estimasi", use_container_width=True, key="calc_budget_btn"):
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

    if st.button("Tutup", use_container_width=True, key="close_budget_dialog"):
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

    if st.button("Lihat Rekomendasi", use_container_width=True, key="quiz_submit_btn"):
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

    if st.button("Tutup", use_container_width=True, key="close_quiz_dialog"):
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
    if st.button("Perencana Itinerary Wisata", use_container_width=True, key="open_itinerary_btn"):
        show_itinerary_planner()
    if st.button("Kalkulator Estimasi Budget", use_container_width=True, key="open_budget_btn"):
        show_budget_calculator()
    if st.button("Kuis Wisata Cocokmu", use_container_width=True, key="open_quiz_btn"):
        show_travel_quiz()
    if st.button("Reset percakapan", use_container_width=True, key="reset_chat_btn"):
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
        if cols[i % 2].button(eq, use_container_width=True, key=f"example_{i}"):
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
        if message.get("sources"):
            with st.expander("Sumber"):
                for s in message["sources"]:
                    st.markdown(f"- [{s['title']}]({s['url']})")

typed_question = st.chat_input("Tanya sesuatu tentang Tapin...")

st.markdown(
    '<div class="disclaimer-text">BETA AI mencari jawaban dari internet secara real-time. '
    "Mohon verifikasi info penting sebelum digunakan.</div>",
    unsafe_allow_html=True,
)

question = clicked_example or typed_question

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
                {"role": "assistant", "content": answer, "sources": [], "images": []}
            )
        else:
            placeholder = st.empty()
            placeholder.markdown(
                '<div class="typing-indicator"><span></span><span></span><span></span></div>',
                unsafe_allow_html=True,
            )
            try:
                answer, sources, images = ask_beta_ai(question, SYSTEM_PROMPT)
            except Exception as e:
                answer = f"Maaf, terjadi kesalahan saat memproses pertanyaan: {e}"
                sources, images = [], []
            placeholder.empty()

            st.markdown(answer)
            render_copy_button(answer, key="live-answer")
            render_images(images)
            if sources:
                with st.expander("Sumber"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']})")

            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": sources, "images": images}
            )

    if clicked_example:
        st.rerun()