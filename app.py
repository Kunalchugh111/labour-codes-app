"""
app.py — Labour Codes Assistant (Streamlit).

Pipeline per question:
  1) CORRECT     — detect and fix typos/misspellings against known legal vocabulary.
  2) SEARCH ALL  — search every loaded code simultaneously (no routing, no dead ends).
  3) RENDER      — grounding text from codes that have hits; no-provision list for those that don't.
  4) STREAM      — single Cerebras call that answers from grounding, cites exact Sections/Rules,
                   and explicitly states which codes have no provision on the topic.

Keys live in st.secrets (server-side):  CEREBRAS_API_KEY
"""

import json
import re
import requests
import streamlit as st

import corpus

# ── Constants ─────────────────────────────────────────────────────────────────
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
MODEL_PRIMARY  = "gpt-oss-120b"
MODEL_FALLBACK = "qwen-3-235b-a22b-instruct-2507"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Labour Codes", page_icon="⚖", layout="centered")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;0,9..144,700;1,9..144,300&family=DM+Sans:wght@400;500;600&display=swap');

:root {
  --blue:         #1E40AF;
  --blue-dark:    #1e3a8a;
  --blue-mid:     #3b82f6;
  --blue-light:   #eff6ff;
  --blue-border:  #bfdbfe;
  --bg:           #ffffff;
  --bg-subtle:    #f8fafc;
  --card:         #ffffff;
  --border:       #e2e8f0;
  --border-s:     #cbd5e1;
  --text:         #0f172a;
  --text-2:       #334155;
  --text-3:       #64748b;
  --text-4:       #94a3b8;
  --green:        #16a34a;
  --green-bg:     #f0fdf4;
  --amber:        #d97706;
  --amber-bg:     #fffbeb;
  --amber-border: #fde68a;
  --shadow-sm:    0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md:    0 4px 20px -4px rgba(30,64,175,0.10);
  --shadow-lg:    0 12px 40px -8px rgba(30,64,175,0.14);
  --r:            cubic-bezier(0.16,1,0.3,1);
}

@keyframes fadeUp   { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeIn   { from{opacity:0} to{opacity:1} }
@keyframes shimmer  { 0%,100%{opacity:.5} 50%{opacity:1} }
@keyframes slideIn  { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }

* { box-sizing: border-box; }

.stApp {
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer { display:none!important; }
.block-container {
  max-width: 780px;
  padding-top: 3.5rem !important;
  padding-bottom: 8rem;
}

/* ── Hero ── */
.lc-hero { margin: 0 0 2.75rem; animation: fadeUp .7s var(--r) both; }

.lc-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--blue);
  background: var(--blue-light);
  border: 1px solid var(--blue-border);
  padding: 4px 13px 4px 10px;
  border-radius: 999px;
  margin-bottom: .85rem;
}
.lc-pill-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--blue-mid);
  animation: shimmer 2s ease-in-out infinite;
}

.lc-title {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 44px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 .55rem;
  letter-spacing: -.03em;
  line-height: 1.08;
}
.lc-title em { font-style: italic; color: var(--blue); font-weight: 300; }

.lc-sub {
  font-size: 15.5px;
  color: var(--text-3);
  line-height: 1.65;
  margin: 0;
  max-width: 510px;
  font-weight: 400;
}

.lc-codes {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 1.4rem;
}
.lc-code-chip {
  font-size: 12px;
  font-weight: 500;
  color: var(--blue-dark);
  background: var(--blue-light);
  border: 1px solid var(--blue-border);
  padding: 5px 14px;
  border-radius: 8px;
  transition: all .2s var(--r);
}

.lc-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border) 15%, var(--border) 85%, transparent);
  margin: 2rem 0 1.75rem;
}

/* ── Alert ── */
.lc-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--blue-light);
  border: 1px solid var(--blue-border);
  border-radius: 10px;
  padding: 13px 16px;
  margin-bottom: 1.25rem;
  font-size: 13.5px;
  color: var(--blue-dark);
  line-height: 1.55;
}
.lc-alert-icon { flex-shrink: 0; font-size: 16px; }

/* ── Correction notice ── */
.lc-correction {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--amber-bg);
  border: 1px solid var(--amber-border);
  border-radius: 10px;
  padding: 11px 15px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #92400e;
  line-height: 1.5;
  animation: fadeIn .3s ease both;
}
.lc-correction-icon { flex-shrink: 0; font-size: 15px; }
.lc-correction strong { color: #78350f; }

/* ── Sample question section ── */
.lc-samples-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-4);
  margin-bottom: 1rem;
}

/* ── Buttons ── */
.stButton > button {
  background: var(--card);
  color: var(--text-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 13px 16px;
  font-size: 13.5px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  text-align: left;
  line-height: 1.45;
  width: 100%;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: all .2s var(--r);
}
.stButton > button:hover {
  background: var(--blue-light);
  border-color: var(--blue-border);
  color: var(--blue-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.stButton > button:active { transform: translateY(0); }
.stButton > button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
  background: transparent;
  border: none;
  padding: .3rem 0;
  animation: fadeUp .4s var(--r) both;
}
[data-testid="stChatMessageContent"] {
  font-size: 15px;
  line-height: 1.72;
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
}
[data-testid="stChatMessageContent"] p { margin: 0 0 .75rem; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0; }
[data-testid="stChatMessageContent"] strong { color: var(--blue-dark); font-weight: 600; }
[data-testid="stChatMessageContent"] em { color: var(--text-2); }
[data-testid="stChatMessageContent"] blockquote {
  border-left: 3px solid var(--blue-border);
  margin: .75rem 0;
  padding: 4px 0 4px 14px;
  color: var(--text-3);
  font-style: italic;
  font-size: 13.5px;
}
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
  padding-left: 1.4rem;
  margin: .5rem 0 .75rem;
}
[data-testid="stChatMessageContent"] li { margin-bottom: .35rem; }
[data-testid="stChatMessageContent"] h3 {
  font-family: 'Fraunces', serif;
  font-size: 15.5px;
  font-weight: 600;
  color: var(--blue-dark);
  margin: 1.1rem 0 .4rem;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--blue-border);
}
[data-testid="stChatMessageContent"] code {
  background: var(--blue-light);
  color: var(--blue-dark);
  padding: 1px 6px;
  border-radius: 5px;
  font-size: 12.5px;
}

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--blue-light);
  border: 1px solid var(--blue-border);
  border-radius: 14px 14px 4px 14px;
  padding: 13px 18px;
  margin-left: 60px;
}

/* Assistant card */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background: var(--card);
  border: 1px solid var(--border);
  border-top: 3px solid var(--blue);
  border-radius: 4px 14px 14px 14px;
  padding: 18px 20px 16px;
  box-shadow: var(--shadow-sm);
  margin-right: 60px;
  transition: box-shadow .3s var(--r);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]):hover {
  box-shadow: var(--shadow-md);
}

/* Source + no-provision labels */
.lc-src-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 13px;
}
.lc-src-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: white;
  background: var(--blue);
  padding: 3px 10px;
  border-radius: 6px;
}
.lc-none-chip {
  font-size: 10.5px;
  font-weight: 500;
  color: var(--text-4);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: 6px;
  font-style: italic;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  transition: all .25s var(--r);
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(30,64,175,.07), var(--shadow-md);
}
[data-testid="stChatInput"] textarea {
  color: var(--text) !important;
  font-size: 15px;
  font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--text-4); }
[data-testid="stBottomBlockContainer"] { background: transparent; }

/* ── Spinner ── */
[data-testid="stSpinner"] > div > div {
  border-color: var(--blue-border) !important;
  border-top-color: var(--blue) !important;
}

/* ── Footer ── */
.lc-foot {
  font-size: 11.5px;
  color: var(--text-4);
  text-align: center;
  margin-top: 2rem;
  font-weight: 400;
  line-height: 1.6;
}

::selection { background: var(--blue); color: #fff; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-s); border-radius: 999px; }
</style>
""", unsafe_allow_html=True)


# ── Resource loading ──────────────────────────────────────────────────────────
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()

CFG, CORPUS_DATA = get_corpus()
LOADED = dict(CORPUS_DATA)


def _api_key() -> str:
    try:
        k = st.secrets.get("CEREBRAS_API_KEY", "")
        return (k.strip() if isinstance(k, str) else "")
    except Exception:
        return ""


# ── LLM — streaming ───────────────────────────────────────────────────────────
def _stream(messages: list[dict], system: str, model: str = MODEL_PRIMARY):
    """
    Generator → yields text fragments for st.write_stream.
    Strips Qwen-3 <think>…</think> blocks on the fly.
    Falls back to MODEL_FALLBACK on HTTP error.
    """
    key = _api_key()
    if not key:
        yield "⚠️  Add **CEREBRAS_API_KEY** in *App → Settings → Secrets* to enable answers."
        return

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": system}] + messages
    body  = {"model": model, "messages": msgs, "max_tokens": 2048,
             "temperature": 0.15, "stream": True}

    def _iter(m, is_retry=False):
        body["model"] = m
        with requests.post(CEREBRAS_URL, headers=headers, json=body,
                           timeout=120, stream=True) as r:
            if r.status_code == 429:
                if not is_retry:
                    yield "\n_⏳ Token rate limit hit — retrying in 15 seconds…_\n\n"
                    import time; time.sleep(15)
                    yield from _iter(MODEL_FALLBACK, is_retry=True)
                else:
                    yield (
                        "⚠️  **Rate limit reached.** The free tier allows 30,000 tokens/minute. "
                        "Please wait ~60 seconds before asking again."
                    )
                return
            r.raise_for_status()
            in_think = False
            for raw in r.iter_lines():
                if not raw:
                    continue
                line = raw.decode() if isinstance(raw, bytes) else raw
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError):
                    continue
                if not delta:
                    continue
                if "<think>" in delta:
                    in_think = True
                if in_think:
                    if "</think>" in delta:
                        in_think = False
                        delta = delta[delta.index("</think>") + 8:]
                    else:
                        continue
                if delta:
                    yield delta

    try:
        yield from _iter(model)
    except requests.HTTPError:
        yield from _iter(MODEL_FALLBACK)
    except requests.RequestException as exc:
        yield f"\n\n⚠️  Connection error: {exc}"


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM = """You are a precise Indian labour law reference assistant for HR professionals and legal teams.

You receive statutory text from India's four Labour Codes and their Central Rules, plus a list of any codes that had NO PROVISION found for the query.

━━ RESPONSE FORMAT — follow this every time ━━

**PART 1 — Plain Answer**
Write a SHORT, practical plain-English summary. Follow this pattern:
- For obligations/procedures: use 4–6 bullet points, each one sentence. Cover who must act, what they must do, key thresholds (numbers, timelines), and consequences.
- For definitions: one short paragraph (3–4 sentences max). State what it includes and what it excludes.
- No citations, no legal jargon, no padding. Be direct.

---

**PART 2 — What the Act Says**
Reproduce the most relevant statutory text under section headings. Format:

> **Section X(Y), [Full Code Title, Year]**
> *"Exact or near-exact text of the provision as it appears in the statute."*

If multiple codes are relevant, group under ### [Code Short Name] headings.
For each code listed as having NO PROVISION, write one line:
> *[Code Name] contains no provision on this topic.*

━━ ABSOLUTE RULES ━━

1. PART 1 must never quote statute — plain English only.
2. PART 2 must reproduce the statutory text faithfully and completely (within what was supplied). Do not paraphrase in Part 2.
3. Source discipline: use only the statutory text supplied. No outside knowledge, case law, or internet.
4. If the answer cannot be found in the supplied text, say so plainly in Part 1 and omit Part 2.
5. Close every answer with this line (verbatim):
   > ⚖️ Informational reference only — the cited statutory provisions are authoritative."""


# ── Pipeline ──────────────────────────────────────────────────────────────────
def build_prompt(query: str, all_results: dict) -> str:
    """Assemble the user message: grounding text + no-provision note + question."""
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
    """Build the amber correction-notice HTML."""
    pairs = ", ".join(
        f'<strong>{orig}</strong> → <strong>{fix}</strong>'
        for orig, fix in corrections
    )
    return (
        f'<div class="lc-correction">'
        f'<span class="lc-correction-icon">✏️</span>'
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


# ── Header ─────────────────────────────────────────────────────────────────────
chips = "".join(
    f'<span class="lc-code-chip">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)
st.markdown(f"""
<div class="lc-hero">
  <div class="lc-pill"><span class="lc-pill-dot"></span>Indian Labour Codes · Legal Reference</div>
  <h1 class="lc-title">Labour Codes <em>Assistant</em></h1>
  <p class="lc-sub">Answers grounded in the four Labour Codes and their Central Rules —
  every response cites the exact Section and Rule number.</p>
  <div class="lc-codes">{chips}</div>
</div>
<div class="lc-divider"></div>
""", unsafe_allow_html=True)

if not _api_key():
    st.markdown(
        '<div class="lc-alert">'
        '<span class="lc-alert-icon">⚙️</span>'
        'Add your <b>CEREBRAS_API_KEY</b> in <em>App → Settings → Secrets</em> to enable answers.'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask anything… e.g. What are the conditions for retrenchment?"):
    _submit(prompt)

# ── Render history ────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="⚖"):
            # Correction notice (if any)
            if msg.get("corrections"):
                st.markdown(_correction_html(msg["corrections"]), unsafe_allow_html=True)
            # Source chips row
            src  = msg.get("sources", [])
            none = msg.get("no_provision", [])
            if src or none:
                src_html  = "".join(f'<span class="lc-src-chip">📋 {s}</span>' for s in src)
                none_html = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in none)
                st.markdown(
                    f'<div class="lc-src-row">{src_html}{none_html}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(msg["content"])

# ── Sample questions (only when no history and nothing pending) ───────────────
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

    # ── Step 1: Typo correction ──
    corrected_q, corrections = corpus.correct_query(raw_q)

    # Show user message (original text)
    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    # ── Step 2: Search all codes using corrected query ──
    with st.spinner("Searching the codes…"):
        all_results = corpus.search_all(LOADED, corrected_q, k=4)

    sources      = [res["meta"]["short"] for res in all_results.values() if res["found"]]
    no_provision = [res["meta"]["short"] for res in all_results.values() if not res["found"]]

    user_msg = build_prompt(corrected_q, all_results)

    with st.chat_message("assistant", avatar="⚖"):
        # Correction notice
        if corrections:
            st.markdown(_correction_html(corrections), unsafe_allow_html=True)

        # Source/no-provision chips
        if sources or no_provision:
            src_html  = "".join(f'<span class="lc-src-chip">📋 {s}</span>' for s in sources)
            none_html = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in no_provision)
            st.markdown(
                f'<div class="lc-src-row">{src_html}{none_html}</div>',
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
    '<div class="lc-foot">'
    'Informational reference for HR &amp; Legal teams · '
    'Powered by Cerebras + Qwen-3 · '
    'Cited statutory provisions are authoritative'
    '</div>',
    unsafe_allow_html=True,
)
