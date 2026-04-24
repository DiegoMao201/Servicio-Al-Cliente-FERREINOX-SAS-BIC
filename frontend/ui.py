import html
import math

import streamlit as st


def inject_brand_theme():
    """Aplica una identidad visual ejecutiva inspirada en Ferreinox."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Sora:wght@500;600;700&display=swap');

            :root {
                --fx-ink: #102033;
                --fx-steel: #29455f;
                --fx-muted: #61778f;
                --fx-sand: #f3efe7;
                --fx-ivory: #fbf8f2;
                --fx-panel: rgba(255, 255, 255, 0.84);
                --fx-border: rgba(16, 32, 51, 0.10);
                --fx-orange: #d96a1d;
                --fx-orange-strong: #b8520f;
                --fx-green: #197a57;
                --fx-red: #bf3d2c;
                --fx-shadow: 0 22px 50px rgba(16, 32, 51, 0.10);
            }

            html, body, [class*="css"] {
                font-family: 'Manrope', sans-serif;
                color: var(--fx-ink);
            }

            [data-testid="stAppViewContainer"] {
                background:
                    radial-gradient(circle at top left, rgba(217, 106, 29, 0.16), transparent 28%),
                    radial-gradient(circle at top right, rgba(25, 122, 87, 0.10), transparent 24%),
                    linear-gradient(180deg, #f7f2e9 0%, #fbfaf7 35%, #f5f7f9 100%);
            }

            [data-testid="stHeader"] {
                background: rgba(0, 0, 0, 0);
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #132739 0%, #17324a 58%, #0e1d2c 100%);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }

            [data-testid="stSidebar"] * {
                color: #eef4f8;
            }

            [data-testid="stSidebarNav"] * {
                color: #eef4f8;
            }

            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] div {
                color: #eef4f8;
            }

            .block-container {
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            .fx-hero {
                padding: 1.6rem 1.8rem 1.4rem;
                border: 1px solid rgba(255, 255, 255, 0.45);
                border-radius: 28px;
                background:
                    linear-gradient(135deg, rgba(16, 32, 51, 0.96), rgba(31, 64, 91, 0.92)),
                    linear-gradient(90deg, rgba(217, 106, 29, 0.22), transparent 48%);
                box-shadow: var(--fx-shadow);
                margin-bottom: 1.2rem;
                position: relative;
                overflow: hidden;
            }

            .fx-hero:before {
                content: '';
                position: absolute;
                inset: auto -30px -60px auto;
                width: 220px;
                height: 220px;
                background: radial-gradient(circle, rgba(217, 106, 29, 0.30), transparent 65%);
            }

            .fx-kicker {
                display: inline-block;
                margin-bottom: 0.65rem;
                padding: 0.28rem 0.7rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.12);
                color: #ffd8bd;
                font-size: 0.76rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .fx-title {
                margin: 0;
                color: #ffffff;
                font-family: 'Sora', sans-serif;
                font-size: 2.2rem;
                line-height: 1.05;
                font-weight: 700;
            }

            .fx-subtitle {
                margin: 0.75rem 0 0;
                max-width: 960px;
                color: rgba(255, 255, 255, 0.80);
                font-size: 1rem;
                line-height: 1.6;
            }

            .fx-badge {
                display: inline-block;
                margin-top: 1rem;
                padding: 0.42rem 0.85rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                font-size: 0.82rem;
                font-weight: 600;
            }

            .fx-section-title {
                margin: 1.25rem 0 0.15rem;
                color: var(--fx-ink);
                font-family: 'Sora', sans-serif;
                font-size: 1.28rem;
                font-weight: 700;
            }

            .fx-section-copy {
                margin: 0 0 0.9rem;
                color: var(--fx-muted);
                font-size: 0.96rem;
            }

            .fx-card {
                min-height: 138px;
                padding: 1rem 1.05rem;
                border: 1px solid var(--fx-border);
                border-radius: 22px;
                background: var(--fx-panel);
                box-shadow: 0 18px 36px rgba(16, 32, 51, 0.06);
                backdrop-filter: blur(10px);
            }

            .fx-card-label {
                color: var(--fx-muted);
                font-size: 0.84rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }

            .fx-card-value {
                margin-top: 0.55rem;
                color: var(--fx-ink);
                font-family: 'Sora', sans-serif;
                font-size: 2rem;
                font-weight: 700;
            }

            .fx-card-caption {
                margin-top: 0.55rem;
                color: var(--fx-muted);
                font-size: 0.9rem;
                line-height: 1.5;
            }

            .fx-strip {
                padding: 1rem 1.1rem;
                border: 1px solid rgba(16, 32, 51, 0.08);
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.78);
                margin-bottom: 0.85rem;
            }

            .fx-strip strong {
                color: var(--fx-ink);
            }

            div[role="tablist"] {
                gap: 0.4rem;
            }

            button[role="tab"] {
                color: #111111 !important;
                background: rgba(255, 255, 255, 0.86) !important;
                border: 1px solid rgba(16, 32, 51, 0.10) !important;
                border-radius: 999px !important;
                padding: 0.5rem 0.95rem !important;
            }

            button[role="tab"] p {
                color: #111111 !important;
                font-weight: 700;
            }

            button[role="tab"][aria-selected="true"] {
                background: #ffffff !important;
                border-color: rgba(217, 106, 29, 0.55) !important;
                box-shadow: 0 10px 22px rgba(16, 32, 51, 0.08);
            }

            .stSelectbox label,
            .stTextArea label,
            .stTextInput label,
            .stRadio label {
                color: var(--fx-ink) !important;
                font-weight: 700;
            }

            .stSelectbox [data-baseweb="select"] > div,
            .stTextArea textarea,
            .stTextInput input {
                color: #111111 !important;
                background: rgba(255, 255, 255, 0.92) !important;
                border-radius: 16px !important;
                border: 1px solid rgba(16, 32, 51, 0.12) !important;
            }

            .fx-pill {
                display: inline-block;
                padding: 0.22rem 0.6rem;
                border-radius: 999px;
                background: rgba(16, 32, 51, 0.08);
                color: var(--fx-ink);
                font-size: 0.76rem;
                font-weight: 700;
                margin-right: 0.35rem;
            }

            .fx-pill.is-good { background: rgba(25, 122, 87, 0.12); color: var(--fx-green); }
            .fx-pill.is-warn { background: rgba(217, 106, 29, 0.14); color: var(--fx-orange-strong); }
            .fx-pill.is-bad { background: rgba(191, 61, 44, 0.12); color: var(--fx-red); }

            .fx-flow {
                padding: 1rem;
                border-radius: 20px;
                min-height: 160px;
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(243, 239, 231, 0.76));
                border: 1px solid rgba(16, 32, 51, 0.08);
                box-shadow: 0 14px 24px rgba(16, 32, 51, 0.05);
            }

            .fx-flow-step {
                color: var(--fx-orange-strong);
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }

            .fx-flow-title {
                margin: 0.4rem 0 0.45rem;
                font-family: 'Sora', sans-serif;
                font-size: 1.05rem;
                font-weight: 700;
                color: var(--fx-ink);
            }

            .fx-flow-copy {
                color: var(--fx-muted);
                font-size: 0.92rem;
                line-height: 1.55;
            }

            .fx-message {
                padding: 0.9rem 1rem;
                border-radius: 18px;
                margin-bottom: 0.65rem;
                border: 1px solid rgba(16, 32, 51, 0.08);
                background: rgba(255, 255, 255, 0.86);
            }

            .fx-message.fx-inbound {
                border-left: 4px solid var(--fx-orange);
            }

            .fx-message.fx-outbound {
                border-left: 4px solid var(--fx-green);
            }

            .fx-message-meta {
                color: var(--fx-muted);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            }

            .fx-message-body {
                margin-top: 0.4rem;
                color: var(--fx-ink);
                font-size: 0.95rem;
                line-height: 1.6;
                white-space: pre-wrap;
            }

            .stButton > button {
                border-radius: 999px;
                border: 1px solid rgba(217, 106, 29, 0.35);
                background: linear-gradient(135deg, var(--fx-orange), var(--fx-orange-strong));
                color: #ffffff;
                font-weight: 700;
                padding: 0.55rem 1rem;
            }

            .stButton > button:hover {
                border-color: rgba(217, 106, 29, 0.6);
                color: #ffffff;
            }

            [data-testid="stDataFrame"] {
                border-radius: 20px;
                overflow: hidden;
                border: 1px solid rgba(16, 32, 51, 0.08);
                box-shadow: 0 10px 26px rgba(16, 32, 51, 0.04);
            }

            .stAlert {
                color: #111111;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_hero(kicker, title, subtitle, badge=None):
    badge_html = f'<div class="fx-badge">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        f"""
        <section class="fx-hero">
            <div class="fx-kicker">{html.escape(kicker)}</div>
            <h1 class="fx-title">{html.escape(title)}</h1>
            <p class="fx-subtitle">{html.escape(subtitle)}</p>
            {badge_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(title, description):
    st.markdown(f'<div class="fx-section-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="fx-section-copy">{html.escape(description)}</p>', unsafe_allow_html=True)


def render_metric_card(label, value, caption):
    st.markdown(
        f"""
        <div class="fx-card">
            <div class="fx-card-label">{html.escape(label)}</div>
            <div class="fx-card-value">{html.escape(str(value))}</div>
            <div class="fx-card-caption">{html.escape(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_highlight(message):
    st.markdown(f'<div class="fx-strip">{message}</div>', unsafe_allow_html=True)


def render_status_pill(label, tone="neutral"):
    tone_class = {
        "good": "is-good",
        "warn": "is-warn",
        "bad": "is-bad",
    }.get(tone, "")
    return f'<span class="fx-pill {tone_class}">{html.escape(label)}</span>'


def render_flow_step(step_number, title, description):
    st.markdown(
        f"""
        <div class="fx-flow">
            <div class="fx-flow-step">Paso {html.escape(str(step_number))}</div>
            <div class="fx-flow-title">{html.escape(title)}</div>
            <div class="fx-flow-copy">{html.escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _normalize_message_content(content):
    if content is None:
        return "Mensaje sin texto adjunto."
    if isinstance(content, str):
        return content
    if isinstance(content, float) and math.isnan(content):
        return "Mensaje sin texto adjunto."
    return str(content)


def render_message(direction, created_at, intent, content):
    direction_label = "Cliente" if direction == "inbound" else "Agente"
    tone_class = "fx-inbound" if direction == "inbound" else "fx-outbound"
    intent_label = intent or "sin clasificar"
    body = _normalize_message_content(content)
    st.markdown(
        f"""
        <div class="fx-message {tone_class}">
            <div class="fx-message-meta">{html.escape(direction_label)} · {html.escape(str(created_at))} · {html.escape(intent_label)}</div>
            <div class="fx-message-body">{html.escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )