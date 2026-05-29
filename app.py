"""
app.py — Labour Codes Assistant (Streamlit)
Backend : AWS Bedrock — global.anthropic.claude-sonnet-4-6
Auth    : AWS_BEARER_TOKEN_BEDROCK in Streamlit secrets
Design  : Legal editorial — deep navy, parchment, gold accent
"""

import json
import os
import re
import boto3
import streamlit as st

import corpus

MODEL_ID = "global.anthropic.claude-sonnet-4-6"

st.set_page_config(
    page_title="Labour Codes Assistant",
    page_icon="⚖️",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — complete ground-up rewrite, every px intentional
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400;1,700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&display=swap');

/* ══ Design Tokens ══════════════════════════════════════════════════════════ */
:root {
  --navy:        #0C1B3A;
  --navy-2:      #142552;
  --navy-3:      #1D3470;
  --navy-4:      #253D8A;
  --gold:        #C9A84C;
  --gold-2:      #E8C97A;
  --gold-pale:   #FBF3DC;
  --gold-border: #E4CE95;
  --parchment:   #F8F6F0;
  --parchment-2: #F2EFE6;
  --parchment-3: #EAE5D8;
  --white:       #FFFFFF;
  --ink:         #0A1525;
  --ink-2:       #1C2D47;
  --slate:       #4A5568;
  --slate-2:     #6B7A8D;
  --slate-3:     #9AA5B4;
  --slate-4:     #C8D0DB;
  --slate-5:     #E4E8EE;
  --green:       #14532D;
  --green-bg:    #F0FBF4;
  --green-b:     #A7F3C2;
  --red:         #7F1D1D;
  --red-bg:      #FFF5F5;
  --red-b:       #FECACA;
  --amber:       #78350F;
  --amber-bg:    #FFFBF0;
  --amber-b:     #FDE68A;

  --ease:        cubic-bezier(0.22, 1, 0.36, 1);
  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);

  --s1: 0 1px 4px rgba(12,27,58,.07);
  --s2: 0 4px 20px rgba(12,27,58,.10);
  --s3: 0 12px 40px rgba(12,27,58,.14);
  --s4: 0 24px 60px rgba(12,27,58,.18);
  --s-gold: 0 4px 24px rgba(201,168,76,.25);
}

/* ══ Global Reset ═══════════════════════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

html, body, .stApp {
  background: var(--parchment) !important;
  font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ── Kill every piece of Streamlit chrome ─────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu, footer { display: none !important; }

/* ── Main content column ─────────────────────────────────────────────────── */
.main .block-container {
  max-width: 820px !important;
  padding: 0 1.5rem 9rem !important;
  margin: 0 auto !important;
}

/* ══ CRITICAL: Fix the black bar at bottom ════════════════════════════════
   Root cause: Streamlit's stBottom uses a pseudo-element or child div that
   inherits a dark background from the app shell. We must override EVERY layer.
   ═════════════════════════════════════════════════════════════════════════ */
[data-testid="stBottom"] {
  background: var(--parchment) !important;
  border-top: none !important;
  box-shadow: none !important;
}
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div,
[data-testid="stBottom"] section,
[data-testid="stBottomBlockContainer"],
.stBottomBlockContainer,
.stBottomBlockContainer > div,
section[data-testid="stBottom"],
section[data-testid="stBottom"] > div {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
}

/* ══ Keyframes ══════════════════════════════════════════════════════════════ */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position: 200% center; }
}
@keyframes breathe {
  0%, 100% { opacity: .5; transform: scale(1); }
  50%       { opacity: 1; transform: scale(1.15); }
}
@keyframes slideRight {
  from { opacity: 0; transform: translateX(-10px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* ══ HERO ════════════════════════════════════════════════════════════════════ */
.lc-hero {
  background: var(--navy);
  margin: 0 -1.5rem 0;
  padding: 0;
  position: relative;
  overflow: hidden;
  animation: fadeIn .6s var(--ease) both;
}

/* Layered atmospheric background */
.lc-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 120% 80% at 110% -10%, rgba(201,168,76,.12) 0%, transparent 50%),
    radial-gradient(ellipse 80% 120% at -10% 110%, rgba(29,52,112,.6) 0%, transparent 55%),
    radial-gradient(ellipse 60% 60% at 80% 80%, rgba(37,61,138,.4) 0%, transparent 50%);
  pointer-events: none;
}

/* Decorative circles */
.lc-hero::after {
  content: '';
  position: absolute;
  right: -80px;
  top: -80px;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  border: 1px solid rgba(201,168,76,.08);
  pointer-events: none;
}

.lc-hero-inner {
  position: relative;
  padding: 3.5rem 3rem 2.75rem;
}

/* Gold top rule */
.lc-hero-rule {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent 0%, var(--gold) 30%, var(--gold-2) 50%, var(--gold) 70%, transparent 100%);
  opacity: .7;
}

/* Circle decoration behind scales icon */
.lc-hero-circle {
  position: absolute;
  right: 2.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 180px;
  height: 180px;
  border-radius: 50%;
  border: 1px solid rgba(201,168,76,.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 72px;
  opacity: .15;
  pointer-events: none;
}

.lc-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .28em;
  text-transform: uppercase;
  color: var(--gold);
  opacity: .8;
  margin-bottom: 1.1rem;
}
.lc-eyebrow-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--gold);
  animation: breathe 2.8s ease-in-out infinite;
}
.lc-eyebrow-line {
  width: 28px; height: 1px;
  background: linear-gradient(90deg, var(--gold), transparent);
  opacity: .5;
}

.lc-title {
  font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
  font-size: clamp(36px, 5.5vw, 56px);
  font-weight: 900;
  color: #fff;
  line-height: 1.05;
  letter-spacing: -.025em;
  margin-bottom: .15em;
}
.lc-title-em {
  font-style: italic;
  font-weight: 700;
  color: rgba(255,255,255,.55);
  display: block;
  font-size: .9em;
  letter-spacing: -.01em;
}

.lc-sub {
  font-size: 13.5px;
  font-weight: 300;
  color: rgba(255,255,255,.42);
  line-height: 1.8;
  max-width: 430px;
  margin: 1rem 0 1.75rem;
  letter-spacing: .01em;
}

/* Code badges in hero */
.lc-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.lc-badge {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: rgba(255,255,255,.5);
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.1);
  padding: 5px 12px;
  border-radius: 3px;
  transition: all .2s var(--ease);
}

/* ══ SEARCH AREA ═════════════════════════════════════════════════════════════
   Streamlit's st.chat_input() is ALWAYS rendered in a sticky bottom container —
   it cannot be placed inside a custom HTML div. So we style the bottom container
   to look like a designed search dock, not an afterthought.
   ═════════════════════════════════════════════════════════════════════════════ */

/* The sticky bottom dock — make it look intentional */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
.stBottomBlockContainer {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
  border-top: 1px solid var(--parchment-3) !important;
  padding-top: .75rem !important;
  padding-bottom: .75rem !important;
  box-shadow: 0 -8px 32px rgba(12,27,58,.06) !important;
}
[data-testid="stBottom"] > *,
[data-testid="stBottom"] > * > *,
[data-testid="stBottomBlockContainer"] > *,
.stBottomBlockContainer > * {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
}

/* The search input styling */
[data-testid="stChatInput"] {
  background: var(--white) !important;
  border: 1.5px solid var(--slate-4) !important;
  border-radius: 14px !important;
  box-shadow: var(--s2) !important;
  transition: border-color .22s var(--ease), box-shadow .22s var(--ease) !important;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--navy-3) !important;
  box-shadow: var(--s2), 0 0 0 4px rgba(29,52,112,.09) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
  font-size: 15px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 400 !important;
  line-height: 1.6 !important;
  padding: 14px 16px !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--slate-3) !important;
  font-style: italic !important;
  font-weight: 300 !important;
}

/* Send button */
[data-testid="stChatInputSubmitButton"] button {
  background: var(--navy) !important;
  border-radius: 10px !important;
  transition: background .18s var(--ease) !important;
}
[data-testid="stChatInputSubmitButton"] button:hover {
  background: var(--navy-3) !important;
}

/* ══ SAMPLE QUESTIONS ═══════════════════════════════════════════════════════ */
.lc-samples-wrap {
  padding: 2rem 0 .5rem;
  animation: fadeUp .5s var(--ease) .1s both;
}
.lc-samples-label {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--slate-3);
  margin-bottom: 1rem;
}

/* Sample buttons */
.stButton > button {
  background: var(--white) !important;
  color: var(--ink-2) !important;
  border: 1px solid var(--slate-5) !important;
  border-left: 3px solid transparent !important;
  border-radius: 10px !important;
  padding: 12px 16px !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  font-family: 'DM Sans', sans-serif !important;
  text-align: left !important;
  line-height: 1.55 !important;
  width: 100% !important;
  box-shadow: var(--s1) !important;
  transition: all .2s var(--ease) !important;
  letter-spacing: .005em !important;
}
.stButton > button:hover {
  background: var(--parchment) !important;
  border-color: var(--gold-border) !important;
  border-left-color: var(--gold) !important;
  color: var(--navy) !important;
  transform: translateX(4px) !important;
  box-shadow: var(--s2) !important;
}

/* ══ ALERTS ═════════════════════════════════════════════════════════════════ */
.lc-alert {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: var(--gold-pale);
  border-left: 3px solid var(--gold);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  margin-bottom: 1.5rem;
  font-size: 13.5px;
  color: var(--amber);
  line-height: 1.6;
}

.lc-correction {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  background: var(--amber-bg);
  border-left: 3px solid var(--gold);
  border-radius: 0 8px 8px 0;
  padding: 10px 15px;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: var(--amber);
  line-height: 1.55;
  animation: fadeIn .3s ease both;
}

/* ══ CLARIFYING UI ══════════════════════════════════════════════════════════ */
.lc-clarify-wrap {
  background: var(--white);
  border: 1px solid var(--slate-5);
  border-top: 3px solid var(--navy);
  border-radius: 4px 14px 14px 14px;
  padding: 22px 24px;
  margin: .5rem 0 .5rem 0;
  margin-right: 40px;
  box-shadow: var(--s2);
  animation: fadeUp .35s var(--ease) both;
}
.lc-clarify-q {
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 14px;
  line-height: 1.5;
}
.lc-clarify-hint {
  font-size: 11.5px;
  color: var(--slate-3);
  margin-top: 10px;
  font-style: italic;
}

/* Chip buttons for clarification — styled differently from sample buttons */
.clarify-chip-row .stButton > button {
  background: var(--parchment) !important;
  color: var(--navy-2) !important;
  border: 1.5px solid var(--gold-border) !important;
  border-left: 1.5px solid var(--gold-border) !important;
  border-radius: 999px !important;
  padding: 7px 18px !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  width: auto !important;
  transform: none !important;
  letter-spacing: .02em !important;
}
.clarify-chip-row .stButton > button:hover {
  background: var(--navy) !important;
  border-color: var(--navy) !important;
  color: #fff !important;
  transform: translateY(-1px) !important;
  box-shadow: var(--s2) !important;
}

/* ══ VERDICT CARD ═══════════════════════════════════════════════════════════ */
.lc-verdict {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 22px;
  border-radius: 10px;
  margin-bottom: 18px;
  border: 1.5px solid;
  animation: fadeUp .3s var(--ease) both;
}
.lc-verdict-icon { font-size: 28px; flex-shrink: 0; line-height: 1; }
.lc-verdict-meta { flex: 1; }
.lc-verdict-title {
  font-size: 10px; font-weight: 700;
  letter-spacing: .18em; text-transform: uppercase;
  margin-bottom: 4px;
}
.lc-verdict-text { font-size: 14px; font-weight: 400; line-height: 1.55; }

.lc-verdict.compliant     { background: var(--green-bg); border-color: var(--green-b); color: var(--green); }
.lc-verdict.non-compliant { background: var(--red-bg);   border-color: var(--red-b);   color: var(--red); }
.lc-verdict.partial       { background: var(--amber-bg); border-color: var(--amber-b); color: var(--amber); }

/* ══ CHAT MESSAGES ══════════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: .25rem 0 !important;
  animation: fadeUp .4s var(--ease) both;
}

/* Hide ALL avatar elements — covers every Streamlit version's data-testid variants */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"],
[class*="avatarImage"],
[class*="avatar"] img,
.stChatMessage [data-testid*="Avatar"] { display: none !important; }

/* User bubble — target by role attribute which is more stable than avatar presence */
[data-testid="stChatMessage"][data-role="user"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--navy) !important;
  border-radius: 20px 20px 5px 20px !important;
  padding: 14px 22px !important;
  margin-left: 80px !important;
  margin-right: 0 !important;
  box-shadow: var(--s3) !important;
}
[data-testid="stChatMessage"][data-role="user"] [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"][data-role="user"] [data-testid="stChatMessageContent"] p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] p {
  color: rgba(255,255,255,.85) !important;
  font-size: 14px !important;
  font-weight: 300 !important;
  line-height: 1.7 !important;
}

/* Assistant card */
[data-testid="stChatMessage"][data-role="assistant"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background: var(--white) !important;
  border: 1px solid var(--slate-5) !important;
  border-top: 3px solid var(--navy) !important;
  border-radius: 4px 20px 20px 20px !important;
  padding: 22px 26px 20px !important;
  margin-right: 40px !important;
  margin-left: 0 !important;
  box-shadow: var(--s2) !important;
  transition: box-shadow .25s var(--ease) !important;
}
[data-testid="stChatMessage"][data-role="assistant"]:hover,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]):hover {
  box-shadow: var(--s3) !important;
}

/* Typography inside chat */
[data-testid="stChatMessageContent"] {
  font-size: 14.5px !important;
  line-height: 1.8 !important;
  color: var(--ink-2) !important;
  font-weight: 300 !important;
  font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stChatMessageContent"] p { margin: 0 0 .65rem !important; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0 !important; }
[data-testid="stChatMessageContent"] strong {
  color: var(--navy) !important;
  font-weight: 600 !important;
}
[data-testid="stChatMessageContent"] em { color: var(--slate) !important; }

/* Blockquote = statute text */
[data-testid="stChatMessageContent"] blockquote {
  border-left: 3px solid var(--gold) !important;
  margin: 1rem 0 !important;
  padding: 10px 0 10px 18px !important;
  color: var(--ink-2) !important;
  font-style: normal !important;
  font-size: 13.5px !important;
  background: var(--gold-pale) !important;
  border-radius: 0 8px 8px 0 !important;
  line-height: 1.75 !important;
}

/* Section headings */
[data-testid="stChatMessageContent"] h3 {
  font-family: 'Playfair Display', serif !important;
  font-size: 16px !important;
  font-weight: 700 !important;
  color: var(--navy) !important;
  margin: 1.5rem 0 .6rem !important;
  padding-bottom: 7px !important;
  border-bottom: 1px solid var(--parchment-3) !important;
}
[data-testid="stChatMessageContent"] h4 {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--slate) !important;
  text-transform: uppercase !important;
  letter-spacing: .08em !important;
  margin: 1.2rem 0 .5rem !important;
}

/* Lists */
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
  padding-left: 1.5rem !important;
  margin: .45rem 0 .8rem !important;
}
[data-testid="stChatMessageContent"] li {
  margin-bottom: .4rem !important;
  line-height: 1.65 !important;
}

/* Code */
[data-testid="stChatMessageContent"] code {
  background: var(--parchment-2) !important;
  color: var(--navy-2) !important;
  padding: 2px 7px !important;
  border-radius: 4px !important;
  font-size: 12px !important;
  font-family: 'SF Mono', 'Fira Code', monospace !important;
  border: 1px solid var(--parchment-3) !important;
}

/* ══ SOURCE CHIPS ROW ═══════════════════════════════════════════════════════ */
.lc-src-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--slate-5);
}
.lc-src-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--slate-3);
  margin-right: 3px;
}
.lc-src-chip {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--white);
  background: var(--navy);
  padding: 4px 11px;
  border-radius: 4px;
}
.lc-none-chip {
  font-size: 10px;
  color: var(--slate-3);
  background: var(--parchment-2);
  border: 1px solid var(--slate-5);
  padding: 4px 11px;
  border-radius: 4px;
  font-style: italic;
}

/* ══ SPINNER ════════════════════════════════════════════════════════════════ */
[data-testid="stSpinner"] > div > div {
  border-color: var(--parchment-3) !important;
  border-top-color: var(--navy) !important;
}

/* ══ FOOTER ═════════════════════════════════════════════════════════════════ */
.lc-footer {
  font-size: 11px;
  color: var(--slate-3);
  text-align: center;
  margin-top: 3rem;
  line-height: 2.2;
  letter-spacing: .04em;
  padding-top: 1.5rem;
  border-top: 1px solid var(--parchment-3);
}
.lc-footer strong { color: var(--slate-2); font-weight: 500; }

/* ══ SCROLLBAR ══════════════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--slate-4); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--slate-3); }

::selection { background: var(--navy); color: #fff; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Corpus loader
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()

CFG, CORPUS_DATA = get_corpus()
LOADED = dict(CORPUS_DATA)


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock client
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_bedrock_client():
    try:
        api_key = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        region  = st.secrets.get("AWS_REGION", "ap-south-1")
        if api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
        return boto3.client("bedrock-runtime", region_name=region)
    except Exception:
        return None

def _has_key() -> bool:
    try:
        k = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        return bool(k and k.strip())
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM = """You are an expert Indian Labour Law compliance assistant for HR managers.

You receive:
- Statutory text from India's four Labour Codes and their Central Rules
- The HR manager's question or situation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DETECT QUERY TYPE — choose ONE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TYPE A — COMPLIANCE CHECK
The HR manager describes something they have done or plan to do.
Examples: "I retrenched X with 2 days notice", "We paid bonus at 8%", "We terminated without cause"

Respond with:
1. VERDICT LINE — one of:
   ✔ COMPLIANT — [one sentence why]
   ✖ NON-COMPLIANT — [one sentence what went wrong]
   ⚠ PARTIALLY COMPLIANT — [one sentence what was right and what was wrong]

2. PLAIN ENGLISH EXPLANATION (3–5 bullet points)
   - What the law requires
   - What the HR manager did right or wrong
   - Exact numbers/timelines required by law
   - What they must do now to remedy (if non-compliant)

3. WHAT THE LAW SAYS (verbatim statutory text only — never paraphrase)
   Format: **Section X / Rule X — [Code Name]**
   > "Exact statutory text"

4. CLOSING LINE:
   > ⚖️ This is informational only. Consult a qualified legal advisor for specific situations.

TYPE B — DEFINITION / INFORMATION
The HR manager asks what something means or what their obligations are.

Respond with:
1. PLAIN ENGLISH ANSWER (2–4 sentences, no jargon)
2. KEY POINTS (3–5 bullets — practical, specific numbers/timelines)
3. WHAT THE LAW SAYS (verbatim statutory text)
   Format: **Section X / Rule X — [Code Name]**
   > "Exact statutory text"
4. CLOSING LINE:
   > ⚖️ This is informational only. Consult a qualified legal advisor for specific situations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NEVER invent statutory text. Only quote what is in the supplied excerpts.
- NEVER paraphrase in the "What the Law Says" section — verbatim only.
- NEVER use outside legal knowledge not in the supplied text.
- If a code has no relevant provision, state: *[Code Name] — no provision found on this topic.*
- Keep plain English sections genuinely plain — no legal jargon.
- Be direct and confident. HR managers need clear answers, not hedging."""


# ─────────────────────────────────────────────────────────────────────────────
# Clarification detection
# ─────────────────────────────────────────────────────────────────────────────
CLARIFY_SYSTEM = """You are a helpful Indian Labour Law assistant.

The HR manager has asked a question. Decide if you need 1–2 clarifying details to give a precise compliance answer.

If the query is already specific enough to answer (e.g. contains numbers, timeframes, specific actions done), respond with:
CLEAR

If you need clarification, respond with JSON only — no other text:
{
  "question": "One short clarifying question (max 12 words)",
  "chips": ["Option 1", "Option 2", "Option 3", "Option 4"]
}

Chips should be short (2–5 words each), mutually exclusive, and cover the most likely scenarios.
Only ask if it materially changes the legal answer. Never ask about the industry or company size unless critical."""

def detect_clarification(query: str) -> dict | None:
    client = get_bedrock_client()
    if not client:
        return None
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "system": CLARIFY_SYSTEM,
        "messages": [{"role": "user", "content": query}],
        "temperature": 0.1,
    })
    try:
        resp = client.invoke_model(
            modelId=MODEL_ID, body=body,
            contentType="application/json", accept="application/json"
        )
        raw = json.loads(resp["body"].read())
        text = raw["content"][0]["text"].strip()
        if text == "CLEAR":
            return None
        data = json.loads(text)
        if "question" in data and "chips" in data:
            return data
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Streaming
# ─────────────────────────────────────────────────────────────────────────────
def _friendly_bedrock_error(e: Exception) -> str:
    """Turn raw AWS errors into clear, actionable guidance for the operator."""
    msg = str(e)
    low = msg.lower()
    if ("payment" in low or "marketplace subscription" in low
            or "invalid_payment_instrument" in low):
        return (
            "\n\n⚠️ **The model isn't active yet — AWS billing needs to be set up.**\n\n"
            "This is an AWS account issue, not this app. To fix it:\n"
            "1. **AWS Console → Billing → Payment preferences** — add a valid card "
            "(not expired; some cards need a small verification charge to clear).\n"
            "2. **Bedrock Console → Model access** (in your `AWS_REGION`) — enable "
            "**Claude Sonnet 4.6** and wait until it reads *Access granted*.\n"
            "3. The card must be on the **same AWS account** that issued your "
            "`AWS_BEARER_TOKEN_BEDROCK`.\n"
            "4. Wait ~2 minutes and try again. If it still fails, open a **free "
            "Billing support case** with AWS."
        )
    if ("accessdenied" in low or "not authorized" in low
            or "could not be validated" in low):
        return (
            "\n\n⚠️ **AWS denied access to the model.** Check that **Claude Sonnet 4.6** "
            "is enabled in **Bedrock → Model access** for your `AWS_REGION`, and that "
            "`AWS_BEARER_TOKEN_BEDROCK` is valid for that account and region."
        )
    return f"\n\n⚠️ Error contacting the model: {msg}"


def _stream(messages: list[dict]):
    client = get_bedrock_client()
    if not client:
        yield "⚠️ Bedrock client error. Check secrets."
        return
    if not _has_key():
        yield "⚠️ Add **AWS_BEARER_TOKEN_BEDROCK** and **AWS_REGION** in *App → Settings → Secrets*."
        return

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": SYSTEM,
        "messages": messages,
        "temperature": 0.1,
    })
    try:
        resp = client.invoke_model_with_response_stream(
            modelId=MODEL_ID, body=body,
            contentType="application/json", accept="application/json",
        )
        for event in resp.get("body", []):
            chunk = event.get("chunk")
            if not chunk:
                continue
            payload = json.loads(chunk["bytes"].decode())
            if payload.get("type") == "content_block_delta":
                delta = payload.get("delta", {})
                if delta.get("type") == "text_delta":
                    t = delta.get("text", "")
                    if t:
                        yield t
    except Exception as e:
        yield _friendly_bedrock_error(e)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def build_prompt(query: str, all_results: dict) -> str:
    grounding = corpus.render_all_results(all_results)
    no_prov   = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
    parts     = [f"=== STATUTORY TEXT ===\n{grounding}"]
    if no_prov:
        parts.append(
            "=== NO PROVISION FOUND ===\n"
            + "\n".join(f"• {n}" for n in no_prov)
        )
    parts.append(f"=== QUESTION ===\n{query}")
    return "\n\n".join(parts)

def _correction_html(corrections):
    pairs = ", ".join(
        f'<strong>{o}</strong> → <strong>{f}</strong>' for o, f in corrections
    )
    return f'<div class="lc-correction">✏️ Interpreted as: {pairs}</div>'

def _src_row_html(sources, no_provision):
    src  = "".join(f'<span class="lc-src-chip">{s}</span>' for s in sources)
    none = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in no_provision)
    return (
        f'<div class="lc-src-row">'
        f'<span class="lc-src-label">Sources</span>{src}{none}'
        f'</div>'
    )

def _verdict_html(text: str) -> str | None:
    m = re.search(
        r'([✔✖⚠])\s*(COMPLIANT|NON-COMPLIANT|PARTIALLY COMPLIANT)\s*[—–-]\s*(.+)',
        text
    )
    if not m:
        return None
    icon, label, detail = m.group(1), m.group(2), m.group(3).strip()
    cls = {"✔": "compliant", "✖": "non-compliant", "⚠": "partial"}.get(icon, "partial")
    return (
        f'<div class="lc-verdict {cls}">'
        f'  <span class="lc-verdict-icon">{icon}</span>'
        f'  <div class="lc-verdict-meta">'
        f'    <div class="lc-verdict-title">{label}</div>'
        f'    <div class="lc-verdict-text">{detail}</div>'
        f'  </div>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("messages", []),
    ("pending", None),
    ("awaiting_clarify", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

def _submit(q: str):
    st.session_state.pending = q

def _clarify_pick(chip: str):
    ctx = st.session_state.awaiting_clarify
    combined = f"{ctx['original_q']} — {chip}"
    st.session_state.awaiting_clarify = None
    st.session_state.pending = combined


# ─────────────────────────────────────────────────────────────────────────────
# ── HERO + SEARCH SECTION ────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
badges_html = "".join(
    f'<span class="lc-badge">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)

st.markdown(f"""
<div class="lc-hero">
  <div class="lc-hero-rule"></div>
  <div class="lc-hero-inner">
    <div class="lc-hero-circle">⚖</div>
    <div class="lc-eyebrow">
      <span class="lc-eyebrow-dot"></span>
      Indian Labour Codes
      <span class="lc-eyebrow-line"></span>
      HR Compliance Reference
    </div>
    <h1 class="lc-title">
      Labour Codes
      <span class="lc-title-em">Assistant</span>
    </h1>
    <p class="lc-sub">
      Ask about compliance, definitions, or obligations — grounded in the four
      Labour Codes with exact Section citations.
    </p>
    <div class="lc-badges">{badges_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Chat input — Streamlit always renders this in a sticky bottom dock ─────
if prompt := st.chat_input(
    "e.g. I retrenched an employee with 2 days notice — was that correct?"
):
    _submit(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# Auth warning
# ─────────────────────────────────────────────────────────────────────────────
if not _has_key():
    st.markdown(
        '<div class="lc-alert" style="margin-top:1.5rem;">'
        '⚙️ Add <strong>AWS_BEARER_TOKEN_BEDROCK</strong> and '
        '<strong>AWS_REGION</strong> in <em>App → Settings → Secrets</em> to activate.'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chat history
# ─────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="⚖️"):
            if msg.get("corrections"):
                st.markdown(_correction_html(msg["corrections"]), unsafe_allow_html=True)
            if msg.get("verdict_html"):
                st.markdown(msg["verdict_html"], unsafe_allow_html=True)
            if msg.get("sources") or msg.get("no_provision"):
                st.markdown(
                    _src_row_html(msg.get("sources", []), msg.get("no_provision", [])),
                    unsafe_allow_html=True,
                )
            st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# Clarification UI
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.awaiting_clarify:
    ctx = st.session_state.awaiting_clarify
    st.markdown(
        f'<div class="lc-clarify-wrap">'
        f'<div class="lc-clarify-q">🤔 {ctx["question"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="clarify-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(ctx["chips"]))
    for i, chip in enumerate(ctx["chips"]):
        cols[i].button(chip, key=f"chip_{i}", on_click=_clarify_pick, args=(chip,))
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="lc-clarify-hint">Or type more details in the search bar above ↑</p>'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sample questions (empty state)
# ─────────────────────────────────────────────────────────────────────────────
if (
    not st.session_state.messages
    and not st.session_state.pending
    and not st.session_state.awaiting_clarify
):
    st.markdown('<div class="lc-samples-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="lc-samples-label">Try asking</div>', unsafe_allow_html=True)
    samples = [
        "I retrenched an employee with 2 days notice — was that correct?",
        "What are the conditions and procedure for retrenchment?",
        "How is 'wages' defined across the four Codes?",
        "Can I terminate an employee during probation without notice?",
        "When is gratuity payable and how is it calculated?",
        "What notice period is required before a lawful strike?",
    ]
    c1, c2 = st.columns(2)
    for i, s in enumerate(samples):
        (c1 if i % 2 == 0 else c2).button(s, key=f"s{i}", on_click=_submit, args=(s,))
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Process pending query
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.pending:
    raw_q = st.session_state.pending
    st.session_state.pending = None

    corrected_q, corrections = corpus.correct_query(raw_q)

    # Show user message
    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    # Check if clarification needed
    is_clarification = " — " not in raw_q
    clarify_data = None
    if is_clarification and _has_key():
        with st.spinner("Thinking…"):
            clarify_data = detect_clarification(corrected_q)

    if clarify_data and st.session_state.awaiting_clarify is None:
        st.session_state.awaiting_clarify = {
            "question":   clarify_data["question"],
            "chips":      clarify_data["chips"],
            "original_q": corrected_q,
        }
        st.rerun()
    else:
        st.session_state.awaiting_clarify = None

        with st.spinner("Searching the codes…"):
            all_results = corpus.search_all(LOADED, corrected_q, k=8)

        sources      = [r["meta"]["short"] for r in all_results.values() if r["found"]]
        no_provision = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
        user_msg     = build_prompt(corrected_q, all_results)

        with st.chat_message("assistant", avatar="⚖️"):
            if corrections:
                st.markdown(_correction_html(corrections), unsafe_allow_html=True)

            verdict_placeholder = st.empty()

            if sources or no_provision:
                st.markdown(
                    _src_row_html(sources, no_provision), unsafe_allow_html=True
                )

            if not sources:
                names    = " · ".join(e["meta"]["short"] for e in LOADED.values())
                response = (
                    f"No relevant provisions found across **{names}** for this query. "
                    "Try rephrasing or ask about a specific Section or topic."
                )
                st.markdown(response)
                verdict_html = None
            else:
                response = st.write_stream(
                    _stream([{"role": "user", "content": user_msg}])
                )
                verdict_html = _verdict_html(response or "")
                if verdict_html:
                    verdict_placeholder.markdown(verdict_html, unsafe_allow_html=True)

        st.session_state.messages.append({
            "role":         "assistant",
            "content":      response,
            "sources":      sources,
            "no_provision": no_provision,
            "corrections":  corrections,
            "verdict_html": verdict_html if sources else None,
        })
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="lc-footer">'
    '<strong>HR Compliance Reference</strong>'
    ' &nbsp;·&nbsp; Claude Sonnet 4.6 via AWS Bedrock'
    ' &nbsp;·&nbsp; Always consult a qualified legal advisor'
    '</div>',
    unsafe_allow_html=True,
)
