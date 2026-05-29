"""
app.py — Labour Codes Assistant (Streamlit)
Backend : AWS Bedrock — claude-sonnet-4-6
Design  : White · Navy Blue · Slate — editorial-legal aesthetic

Secrets required in Streamlit (App → Settings → Secrets):
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION          (e.g. us-east-1)
"""

import json
import re
import boto3
import streamlit as st

import corpus

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_ID = "us.anthropic.claude-sonnet-4-6-20250514-v1:0"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Labour Codes — Legal Reference",
    page_icon="⚖️",
    layout="centered",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Sora:wght@300;400;500;600&display=swap');

:root {
  /* Palette */
  --navy:          #0f2557;
  --navy-mid:      #1e3a8a;
  --navy-light:    #dbeafe;
  --navy-xlight:   #eff6ff;
  --navy-border:   #bfdbfe;
  --slate:         #475569;
  --slate-light:   #f1f5f9;
  --slate-border:  #e2e8f0;
  --slate-muted:   #94a3b8;
  --white:         #ffffff;
  --ink:           #0a1628;
  --ink-2:         #1e293b;
  --ink-3:         #334155;

  /* Shadows */
  --shadow-xs:  0 1px 2px rgba(15,37,87,0.06);
  --shadow-sm:  0 2px 8px rgba(15,37,87,0.08);
  --shadow-md:  0 8px 32px rgba(15,37,87,0.12);
  --shadow-lg:  0 20px 60px rgba(15,37,87,0.16);

  /* Motion */
  --ease: cubic-bezier(0.16,1,0.3,1);
}

/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

.stApp {
  background: var(--white);
  font-family: 'Sora', system-ui, sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}

[data-testid="stHeader"],
[data-testid="stToolbar"],
#MainMenu, footer { display: none !important; }

.block-container {
  max-width: 800px !important;
  padding-top: 0 !important;
  padding-bottom: 9rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
}

/* ── Keyframes ── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50%       { opacity: 1;   transform: scale(1); }
}
@keyframes shimmer-line {
  0%   { background-position: -600px 0; }
  100% { background-position: 600px 0; }
}

/* ══════════════════════════════════════════════
   HERO SECTION
══════════════════════════════════════════════ */
.lc-hero-wrap {
  position: relative;
  padding: 4rem 0 2.5rem;
  animation: fadeUp 0.8s var(--ease) both;
  overflow: hidden;
}

/* Decorative rule line behind title */
.lc-hero-wrap::before {
  content: '';
  position: absolute;
  top: 5.2rem;
  left: -1.5rem;
  right: -1.5rem;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--navy-border) 20%, var(--navy-border) 80%, transparent);
  opacity: 0.6;
}

.lc-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--navy-mid);
  margin-bottom: 1.1rem;
}

.lc-eyebrow-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--navy-mid);
  animation: pulse-dot 2.4s ease-in-out infinite;
}

.lc-eyebrow-line {
  display: inline-block;
  width: 28px;
  height: 1.5px;
  background: var(--navy-mid);
  opacity: 0.5;
}

.lc-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: clamp(36px, 5vw, 52px);
  font-weight: 700;
  color: var(--navy);
  line-height: 1.05;
  letter-spacing: -0.02em;
  margin-bottom: 0.2rem;
}

.lc-title-italic {
  font-style: italic;
  font-weight: 400;
  color: var(--slate);
}

.lc-sub {
  font-size: 15px;
  font-weight: 300;
  color: var(--slate);
  line-height: 1.7;
  max-width: 520px;
  margin-top: 1rem;
}

/* Code chips row */
.lc-codes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 1.6rem;
}

.lc-code-chip {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--navy-mid);
  background: var(--navy-xlight);
  border: 1px solid var(--navy-border);
  padding: 5px 14px;
  border-radius: 4px;
}

/* ── Divider ── */
.lc-rule {
  height: 1px;
  background: var(--slate-border);
  margin: 2.25rem 0 2rem;
  opacity: 0.7;
}

/* ══════════════════════════════════════════════
   ALERT / NOTICE BANNERS
══════════════════════════════════════════════ */
.lc-alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: var(--navy-xlight);
  border-left: 3px solid var(--navy-mid);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  margin-bottom: 1.5rem;
  font-size: 13.5px;
  color: var(--navy);
  line-height: 1.6;
}

.lc-correction {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #fefce8;
  border-left: 3px solid #ca8a04;
  border-radius: 0 8px 8px 0;
  padding: 11px 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #713f12;
  line-height: 1.55;
  animation: fadeIn 0.3s ease both;
}

/* ══════════════════════════════════════════════
   SAMPLE QUESTIONS
══════════════════════════════════════════════ */
.lc-samples-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--slate-muted);
  margin-bottom: 1rem;
}

.stButton > button {
  background: var(--white);
  color: var(--ink-3);
  border: 1px solid var(--slate-border);
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 400;
  font-family: 'Sora', sans-serif;
  text-align: left;
  line-height: 1.5;
  width: 100%;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: all 0.22s var(--ease);
  position: relative;
  overflow: hidden;
}

.stButton > button::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--navy-mid);
  opacity: 0;
  transition: opacity 0.2s ease;
  border-radius: 0;
}

.stButton > button:hover {
  background: var(--navy-xlight);
  border-color: var(--navy-border);
  color: var(--navy);
  transform: translateX(2px);
  box-shadow: var(--shadow-sm);
}

.stButton > button:hover::before { opacity: 1; }
.stButton > button:active { transform: translateX(1px); box-shadow: var(--shadow-xs); }
.stButton > button:focus-visible { outline: 2px solid var(--navy-mid); outline-offset: 2px; }

/* ══════════════════════════════════════════════
   CHAT MESSAGES
══════════════════════════════════════════════ */
[data-testid="stChatMessage"] {
  background: transparent;
  border: none;
  padding: 0.2rem 0;
  animation: fadeUp 0.4s var(--ease) both;
}

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--navy);
  border-radius: 16px 16px 4px 16px;
  padding: 14px 20px;
  margin-left: 80px;
  box-shadow: var(--shadow-sm);
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
[data-testid="stChatMessageContent"] {
  color: rgba(255,255,255,0.92) !important;
  font-size: 14.5px;
  line-height: 1.65;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
[data-testid="stChatMessageContent"] p {
  color: rgba(255,255,255,0.92) !important;
}

/* Assistant card */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background: var(--white);
  border: 1px solid var(--slate-border);
  border-radius: 4px 16px 16px 16px;
  padding: 22px 24px 18px;
  margin-right: 40px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.3s var(--ease);
  position: relative;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--navy) 0%, var(--navy-mid) 50%, #60a5fa 100%);
  border-radius: 4px 16px 0 0;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]):hover {
  box-shadow: var(--shadow-md);
}

/* Message content typography */
[data-testid="stChatMessageContent"] {
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--ink-2);
  font-family: 'Sora', sans-serif;
  font-weight: 300;
}

[data-testid="stChatMessageContent"] p { margin: 0 0 0.7rem; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0; }

[data-testid="stChatMessageContent"] strong {
  color: var(--navy);
  font-weight: 600;
}

[data-testid="stChatMessageContent"] em {
  color: var(--slate);
  font-style: italic;
}

[data-testid="stChatMessageContent"] blockquote {
  border-left: 2px solid var(--slate-border);
  margin: 0.8rem 0;
  padding: 6px 0 6px 16px;
  color: var(--slate);
  font-style: italic;
  font-size: 13.5px;
  font-weight: 300;
  background: var(--slate-light);
  border-radius: 0 6px 6px 0;
}

[data-testid="stChatMessageContent"] h3 {
  font-family: 'Playfair Display', serif;
  font-size: 15px;
  font-weight: 700;
  color: var(--navy);
  margin: 1.25rem 0 0.5rem;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--navy-border);
  letter-spacing: -0.01em;
}

[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
  padding-left: 1.5rem;
  margin: 0.5rem 0 0.75rem;
}

[data-testid="stChatMessageContent"] li { margin-bottom: 0.4rem; }

[data-testid="stChatMessageContent"] code {
  background: var(--navy-xlight);
  color: var(--navy);
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* Source chips */
.lc-src-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--slate-border);
}

.lc-src-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--slate-muted);
  margin-right: 4px;
}

.lc-src-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--white);
  background: var(--navy);
  padding: 4px 11px;
  border-radius: 4px;
}

.lc-none-chip {
  font-size: 10.5px;
  font-weight: 400;
  color: var(--slate-muted);
  background: var(--slate-light);
  border: 1px solid var(--slate-border);
  padding: 4px 11px;
  border-radius: 4px;
  font-style: italic;
}

/* ══════════════════════════════════════════════
   CHAT INPUT
══════════════════════════════════════════════ */
[data-testid="stChatInput"] {
  background: var(--white) !important;
  border: 1.5px solid var(--slate-border) !important;
  border-radius: 12px !important;
  box-shadow: var(--shadow-sm) !important;
  transition: all 0.25s var(--ease) !important;
}

[data-testid="stChatInput"]:focus-within {
  border-color: var(--navy-mid) !important;
  box-shadow: 0 0 0 4px rgba(30,58,138,0.08), var(--shadow-md) !important;
}

[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
  font-size: 14.5px !important;
  font-family: 'Sora', sans-serif !important;
  font-weight: 300 !important;
}

[data-testid="stChatInput"] textarea::placeholder {
  color: var(--slate-muted) !important;
}

[data-testid="stBottomBlockContainer"] {
  background: linear-gradient(to top, var(--white) 75%, transparent) !important;
  padding-top: 1.5rem !important;
}

/* ══════════════════════════════════════════════
   SPINNER
══════════════════════════════════════════════ */
[data-testid="stSpinner"] > div > div {
  border-color: var(--slate-border) !important;
  border-top-color: var(--navy-mid) !important;
}

/* ══════════════════════════════════════════════
   FOOTER
══════════════════════════════════════════════ */
.lc-footer {
  font-size: 11px;
  font-weight: 400;
  color: var(--slate-muted);
  text-align: center;
  margin-top: 2.5rem;
  letter-spacing: 0.04em;
  line-height: 1.8;
}

.lc-footer-divider {
  display: inline-block;
  margin: 0 8px;
  opacity: 0.4;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--slate-border); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--slate); }

::selection { background: var(--navy); color: var(--white); }
</style>
""", unsafe_allow_html=True)


# ── Corpus loading ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()

CFG, CORPUS_DATA = get_corpus()
LOADED = dict(CORPUS_DATA)


# ── AWS Bedrock client ─────────────────────────────────────────────────────────
@st.cache_resource
def get_bedrock_client():
    try:
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=st.secrets.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=st.secrets.get("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=st.secrets.get("AWS_SECRET_ACCESS_KEY", ""),
        )
    except Exception:
        return None


def _has_credentials() -> bool:
    try:
        k = st.secrets.get("AWS_ACCESS_KEY_ID", "")
        s = st.secrets.get("AWS_SECRET_ACCESS_KEY", "")
        return bool(k and s and k.strip() and s.strip())
    except Exception:
        return False


# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM = """You are a precise Indian labour law reference assistant for HR professionals and legal teams.

You receive statutory text from India's four Labour Codes and their Central Rules, plus a list of any codes that had NO PROVISION found for the query.

━━ YOUR RESPONSE MUST HAVE EXACTLY THESE THREE BLOCKS IN ORDER ━━

════════════════════════════════
BLOCK 1 — PLAIN ANSWER
════════════════════════════════
Short, practical plain-English summary. No citations, no jargon.
- Obligations/procedures → 4–6 bullet points, one sentence each, covering who acts, what they do, key numbers/timelines, consequences.
- Definitions → one paragraph, 3–4 sentences, stating what is included and excluded.

════════════════════════════════
BLOCK 2 — WHAT THE ACT SAYS
════════════════════════════════
YOU MUST WRITE THIS BLOCK. It is not optional. Do not skip it.
Copy the statutory text from the supplied excerpts. Format each provision as:

**Section X(Y) / Rule X(Y) — [Code Short Name]**
> "Exact text of the provision as supplied."

Group by code if multiple codes are relevant. Use ### [Code Short Name] as a heading for each group.
For every code listed as having NO PROVISION, add one line:
> *[Code Name] — no provision found on this topic.*

════════════════════════════════
BLOCK 3 — CLOSING LINE
════════════════════════════════
> ⚖️ Informational reference only — the cited statutory provisions are authoritative.

━━ RULES ━━
1. Block 1: plain English only — never quote statute here.
2. Block 2: reproduce statutory text faithfully — never paraphrase here.
3. Use only the supplied statutory text. No outside knowledge or case law.
4. Exception — if zero statutory text was supplied: write Block 1 saying so, skip Block 2, write Block 3.
5. Never write Block 3 before Block 2 is complete."""


# ── Streaming via Bedrock ──────────────────────────────────────────────────────
def _stream(messages: list[dict], system: str):
    """Generator → yields text fragments for st.write_stream."""
    client = get_bedrock_client()
    if not client:
        yield "⚠️  Could not initialise the AWS Bedrock client. Check your secrets."
        return
    if not _has_credentials():
        yield "⚠️  Add **AWS_ACCESS_KEY_ID**, **AWS_SECRET_ACCESS_KEY**, and **AWS_REGION** in *App → Settings → Secrets*."
        return

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
        "temperature": 0.15,
    }

    try:
        response = client.invoke_model_with_response_stream(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        stream = response.get("body")
        if not stream:
            yield "⚠️  Empty response from Bedrock."
            return

        for event in stream:
            chunk = event.get("chunk")
            if not chunk:
                continue
            payload = json.loads(chunk["bytes"].decode("utf-8"))
            event_type = payload.get("type", "")
            if event_type == "content_block_delta":
                delta = payload.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield text
            elif event_type == "message_stop":
                break

    except client.exceptions.ValidationException as e:
        yield f"\n\n⚠️  Validation error: {e}"
    except client.exceptions.ModelNotReadyException:
        yield "\n\n⚠️  Model not ready. Please try again in a moment."
    except Exception as e:
        yield f"\n\n⚠️  Bedrock error: {e}"


# ── Pipeline helpers ───────────────────────────────────────────────────────────
def build_prompt(query: str, all_results: dict) -> str:
    grounding = corpus.render_all_results(all_results)
    no_prov = [res["meta"]["short"] for res in all_results.values() if not res["found"]]
    parts = [f"=== STATUTORY TEXT ===\n{grounding}"]
    if no_prov:
        parts.append(
            "=== NO PROVISION FOUND IN THESE CODES ===\n"
            + "\n".join(f"• {n}" for n in no_prov)
            + "\n(State this explicitly in your answer for each.)"
        )
    parts.append(f"=== QUESTION ===\n{query}")
    return "\n\n".join(parts)


def _correction_html(corrections: list[tuple[str, str]]) -> str:
    pairs = ", ".join(
        f'<strong>{orig}</strong> → <strong>{fix}</strong>'
        for orig, fix in corrections
    )
    return (
        f'<div class="lc-correction">'
        f'<span>✏️</span> '
        f'Interpreted as: {pairs}'
        f'</div>'
    )


# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []
if "pending" not in st.session_state:
    st.session_state.pending: str | None = None


def _submit(q: str):
    st.session_state.pending = q


# ══════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════
chips_html = "".join(
    f'<span class="lc-code-chip">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)

st.markdown(f"""
<div class="lc-hero-wrap">
  <div class="lc-eyebrow">
    <span class="lc-eyebrow-dot"></span>
    Indian Labour Codes
    <span class="lc-eyebrow-line"></span>
    Legal Reference
  </div>
  <h1 class="lc-title">Labour Codes<br><span class="lc-title-italic">Assistant</span></h1>
  <p class="lc-sub">
    Every answer grounded in the four Labour Codes and their Central Rules —
    precise Section and Rule citations, every time.
  </p>
  <div class="lc-codes">{chips_html}</div>
</div>
""", unsafe_allow_html=True)

if not _has_credentials():
    st.markdown(
        '<div class="lc-alert">'
        '⚙️&nbsp;&nbsp;Add <strong>AWS_ACCESS_KEY_ID</strong>, '
        '<strong>AWS_SECRET_ACCESS_KEY</strong>, and <strong>AWS_REGION</strong> '
        'in <em>App → Settings → Secrets</em> to enable answers.'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="lc-rule"></div>', unsafe_allow_html=True)

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask anything — e.g. What are the conditions for retrenchment?"):
    _submit(prompt)

# ── Render history ────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="⚖️"):
            if msg.get("corrections"):
                st.markdown(_correction_html(msg["corrections"]), unsafe_allow_html=True)
            src  = msg.get("sources", [])
            none = msg.get("no_provision", [])
            if src or none:
                src_html  = "".join(f'<span class="lc-src-chip">📋 {s}</span>' for s in src)
                none_html = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in none)
                st.markdown(
                    f'<div class="lc-src-row">'
                    f'<span class="lc-src-label">Sources</span>'
                    f'{src_html}{none_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(msg["content"])

# ── Sample questions ──────────────────────────────────────────────────────────
if not st.session_state.messages and not st.session_state.pending:
    st.markdown('<div class="lc-samples-label">Try asking</div>', unsafe_allow_html=True)
    samples = [
        "What are the conditions and procedure for retrenchment?",
        "I have retrenched an employee — what are all my legal obligations?",
        "How is 'wages' defined differently across the four Codes?",
        "What notice period is required before a lawful strike?",
        "When is an employee eligible for gratuity and how is it calculated?",
        "What are an employer's obligations under the Code on Social Security?",
    ]
    c1, c2 = st.columns(2)
    for i, s in enumerate(samples):
        (c1 if i % 2 == 0 else c2).button(s, key=f"samp{i}", on_click=_submit, args=(s,))

# ── Process pending question ──────────────────────────────────────────────────
if st.session_state.pending:
    raw_q = st.session_state.pending
    st.session_state.pending = None

    corrected_q, corrections = corpus.correct_query(raw_q)

    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    with st.spinner("Searching the codes…"):
        all_results = corpus.search_all(LOADED, corrected_q, k=4)

    sources      = [res["meta"]["short"] for res in all_results.values() if res["found"]]
    no_provision = [res["meta"]["short"] for res in all_results.values() if not res["found"]]
    user_msg     = build_prompt(corrected_q, all_results)

    with st.chat_message("assistant", avatar="⚖️"):
        if corrections:
            st.markdown(_correction_html(corrections), unsafe_allow_html=True)

        if sources or no_provision:
            src_html  = "".join(f'<span class="lc-src-chip">📋 {s}</span>' for s in sources)
            none_html = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in no_provision)
            st.markdown(
                f'<div class="lc-src-row">'
                f'<span class="lc-src-label">Sources</span>'
                f'{src_html}{none_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

        if not sources:
            loaded_names = " · ".join(e["meta"]["short"] for e in LOADED.values())
            response = (
                f"No relevant provisions were found across any of the loaded codes "
                f"(**{loaded_names}**) for this query. "
                "Please try rephrasing, or ask about a specific Section or topic covered by these Codes."
            )
            st.markdown(response)
        else:
            response = st.write_stream(
                _stream([{"role": "user", "content": user_msg}], system=SYSTEM)
            )

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "sources": sources,
        "no_provision": no_provision,
        "corrections": corrections,
    })
    st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="lc-footer">'
    'Informational reference for HR &amp; Legal teams'
    '<span class="lc-footer-divider">·</span>'
    'Powered by Claude Sonnet 4.6 via AWS Bedrock'
    '<span class="lc-footer-divider">·</span>'
    'Cited statutory provisions are authoritative'
    '</div>',
    unsafe_allow_html=True,
)
