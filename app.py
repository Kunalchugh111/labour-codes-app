"""
app.py — Labour Codes Assistant (Streamlit)
Backend : AWS Bedrock — global.anthropic.claude-sonnet-4-6 (Mumbai cross-region)
Auth    : AWS Bedrock API Key  →  set AWS_BEARER_TOKEN_BEDROCK in Streamlit secrets
Design  : Navy · White · Slate — editorial legal aesthetic
"""

import json
import os
import boto3
import streamlit as st

import corpus

# ── Model ─────────────────────────────────────────────────────────────────────
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Labour Codes — Legal Reference",
    page_icon="⚖️",
    layout="centered",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --navy:         #0f2557;
  --navy-mid:     #1e3a8a;
  --navy-soft:    #3b5bdb;
  --navy-light:   #dbeafe;
  --navy-xlight:  #eff6ff;
  --navy-border:  #bfdbfe;
  --slate:        #475569;
  --slate-light:  #f1f5f9;
  --slate-border: #e2e8f0;
  --slate-muted:  #94a3b8;
  --white:        #ffffff;
  --ink:          #0a1628;
  --ink-2:        #1e293b;
  --ink-3:        #334155;
  --ease:         cubic-bezier(0.16,1,0.3,1);
  --sh-xs:        0 1px 3px rgba(15,37,87,0.07);
  --sh-sm:        0 2px 10px rgba(15,37,87,0.09);
  --sh-md:        0 8px 32px rgba(15,37,87,0.13);
}

*,*::before,*::after{box-sizing:border-box;}

.stApp{
  background:#f8fafc;
  font-family:'DM Sans',system-ui,sans-serif;
  color:var(--ink);
  -webkit-font-smoothing:antialiased;
}

[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important;}

.block-container{
  max-width:780px!important;
  padding:0 1.5rem 9rem!important;
}

/* ── Animations ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes blink{0%,100%{opacity:.35;transform:scale(.8)}50%{opacity:1;transform:scale(1)}}

/* ══ HERO ══════════════════════════════════════════ */
.lc-hero{
  background:var(--navy);
  border-radius:0 0 24px 24px;
  padding:3rem 2.5rem 2.5rem;
  margin:0 -1.5rem 2rem;
  position:relative;
  overflow:hidden;
  animation:fadeIn .6s var(--ease) both;
}
.lc-hero::before{
  content:'';
  position:absolute;inset:0;
  background:radial-gradient(ellipse 70% 80% at 95% 10%,rgba(59,91,219,.35) 0%,transparent 70%),
             radial-gradient(ellipse 50% 60% at 5% 90%,rgba(30,58,138,.4) 0%,transparent 60%);
}
.lc-hero>*{position:relative;}

.lc-eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:10px;font-weight:600;letter-spacing:.2em;
  text-transform:uppercase;color:rgba(255,255,255,.55);
  margin-bottom:.9rem;
}
.lc-dot{
  width:6px;height:6px;border-radius:50%;
  background:#60a5fa;
  animation:blink 2.2s ease-in-out infinite;
}

.lc-title{
  font-family:'Playfair Display',Georgia,serif;
  font-size:clamp(34px,5vw,50px);
  font-weight:700;
  color:#fff;
  line-height:1.06;
  letter-spacing:-.025em;
  margin:0 0 .25rem;
}
.lc-title em{
  font-style:italic;
  font-weight:400;
  color:rgba(255,255,255,.7);
}

.lc-sub{
  font-size:14px;font-weight:300;
  color:rgba(255,255,255,.6);
  line-height:1.7;max-width:500px;
  margin:.8rem 0 1.6rem;
}

.lc-codes{display:flex;flex-wrap:wrap;gap:7px;}
.lc-code-chip{
  font-size:10.5px;font-weight:500;letter-spacing:.05em;
  color:rgba(255,255,255,.75);
  background:rgba(255,255,255,.1);
  border:1px solid rgba(255,255,255,.18);
  padding:5px 13px;border-radius:6px;
  backdrop-filter:blur(4px);
}

/* ══ ALERTS ════════════════════════════════════════ */
.lc-alert{
  display:flex;align-items:flex-start;gap:11px;
  background:var(--navy-xlight);
  border-left:3px solid var(--navy-mid);
  border-radius:0 10px 10px 0;
  padding:14px 18px;margin-bottom:1.5rem;
  font-size:13.5px;color:var(--navy);line-height:1.6;
}
.lc-correction{
  display:flex;align-items:flex-start;gap:9px;
  background:#fefce8;border-left:3px solid #ca8a04;
  border-radius:0 8px 8px 0;
  padding:10px 15px;margin-bottom:12px;
  font-size:12.5px;color:#713f12;line-height:1.55;
  animation:fadeIn .3s ease both;
}

/* ══ SAMPLE QUESTIONS ══════════════════════════════ */
.lc-samples-label{
  font-size:10px;font-weight:600;letter-spacing:.18em;
  text-transform:uppercase;color:var(--slate-muted);
  margin-bottom:.9rem;
}

.stButton>button{
  background:var(--white)!important;
  color:var(--ink-3)!important;
  border:1px solid var(--slate-border)!important;
  border-radius:10px!important;
  padding:13px 16px!important;
  font-size:13px!important;font-weight:400!important;
  font-family:'DM Sans',sans-serif!important;
  text-align:left!important;line-height:1.5!important;
  width:100%!important;cursor:pointer!important;
  box-shadow:var(--sh-xs)!important;
  transition:all .2s var(--ease)!important;
}
.stButton>button:hover{
  background:var(--navy-xlight)!important;
  border-color:var(--navy-border)!important;
  color:var(--navy)!important;
  transform:translateY(-1px)!important;
  box-shadow:var(--sh-sm)!important;
}

/* ══ CHAT MESSAGES ══════════════════════════════════ */
[data-testid="stChatMessage"]{
  background:transparent;border:none;
  padding:.15rem 0;
  animation:fadeUp .35s var(--ease) both;
}

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
  background:var(--navy)!important;
  border-radius:18px 18px 4px 18px!important;
  padding:13px 20px!important;
  margin-left:72px!important;
  box-shadow:var(--sh-sm)!important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
[data-testid="stChatMessageContent"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
[data-testid="stChatMessageContent"] p{
  color:rgba(255,255,255,.9)!important;
  font-size:14px!important;line-height:1.65!important;
}

/* Assistant card */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){
  background:var(--white)!important;
  border:1px solid var(--slate-border)!important;
  border-top:3px solid var(--navy)!important;
  border-radius:4px 18px 18px 18px!important;
  padding:20px 24px 16px!important;
  margin-right:36px!important;
  box-shadow:var(--sh-sm)!important;
  transition:box-shadow .25s var(--ease)!important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]):hover{
  box-shadow:var(--sh-md)!important;
}

/* Typography inside assistant card */
[data-testid="stChatMessageContent"]{
  font-size:14.5px!important;line-height:1.78!important;
  color:var(--ink-2)!important;font-weight:300!important;
}
[data-testid="stChatMessageContent"] p{margin:0 0 .65rem!important;}
[data-testid="stChatMessageContent"] p:last-child{margin-bottom:0!important;}
[data-testid="stChatMessageContent"] strong{color:var(--navy)!important;font-weight:600!important;}
[data-testid="stChatMessageContent"] em{color:var(--slate)!important;}
[data-testid="stChatMessageContent"] blockquote{
  border-left:2px solid var(--navy-border)!important;
  margin:.7rem 0!important;padding:5px 0 5px 14px!important;
  color:var(--slate)!important;font-style:italic!important;
  font-size:13.5px!important;
  background:var(--navy-xlight)!important;
  border-radius:0 6px 6px 0!important;
}
[data-testid="stChatMessageContent"] h3{
  font-family:'Playfair Display',serif!important;
  font-size:15px!important;font-weight:700!important;
  color:var(--navy)!important;
  margin:1.2rem 0 .45rem!important;
  padding-bottom:5px!important;
  border-bottom:1px solid var(--navy-border)!important;
}
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol{
  padding-left:1.4rem!important;margin:.4rem 0 .7rem!important;
}
[data-testid="stChatMessageContent"] li{margin-bottom:.35rem!important;}
[data-testid="stChatMessageContent"] code{
  background:var(--navy-xlight)!important;
  color:var(--navy)!important;
  padding:2px 6px!important;border-radius:4px!important;
  font-size:12px!important;
}

/* Source chips row */
.lc-src-row{
  display:flex;flex-wrap:wrap;align-items:center;gap:6px;
  margin-bottom:14px;padding-bottom:13px;
  border-bottom:1px solid var(--slate-border);
}
.lc-src-label{
  font-size:9.5px;font-weight:600;letter-spacing:.14em;
  text-transform:uppercase;color:var(--slate-muted);margin-right:3px;
}
.lc-src-chip{
  font-size:10px;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase;color:#fff;
  background:var(--navy);padding:4px 11px;border-radius:5px;
}
.lc-none-chip{
  font-size:10px;font-weight:400;color:var(--slate-muted);
  background:var(--slate-light);border:1px solid var(--slate-border);
  padding:4px 11px;border-radius:5px;font-style:italic;
}

/* ══ CHAT INPUT ═════════════════════════════════════ */
[data-testid="stChatInput"]{
  background:var(--white)!important;
  border:1.5px solid var(--slate-border)!important;
  border-radius:14px!important;
  box-shadow:var(--sh-sm)!important;
  transition:all .22s var(--ease)!important;
}
[data-testid="stChatInput"]:focus-within{
  border-color:var(--navy-mid)!important;
  box-shadow:0 0 0 3px rgba(30,58,138,.09),var(--sh-md)!important;
}
[data-testid="stChatInput"] textarea{
  color:var(--ink)!important;
  font-size:14.5px!important;
  font-family:'DM Sans',sans-serif!important;
}
[data-testid="stChatInput"] textarea::placeholder{color:var(--slate-muted)!important;}
[data-testid="stBottomBlockContainer"]{
  background:linear-gradient(to top,#f8fafc 70%,transparent)!important;
  padding-top:1.25rem!important;
}

/* ══ SPINNER ════════════════════════════════════════ */
[data-testid="stSpinner"]>div>div{
  border-color:var(--slate-border)!important;
  border-top-color:var(--navy-mid)!important;
}

/* ══ FOOTER ═════════════════════════════════════════ */
.lc-footer{
  font-size:11px;color:var(--slate-muted);
  text-align:center;margin-top:2.5rem;
  line-height:1.9;letter-spacing:.03em;
}
.lc-footer span{margin:0 7px;opacity:.4;}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--slate-border);border-radius:999px;}
::selection{background:var(--navy);color:#fff;}
</style>
""", unsafe_allow_html=True)


# ── Corpus ────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()

CFG, CORPUS_DATA = get_corpus()
LOADED = dict(CORPUS_DATA)


# ── Bedrock client (API key auth) ─────────────────────────────────────────────
@st.cache_resource
def get_bedrock_client():
    try:
        api_key = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        region  = st.secrets.get("AWS_REGION", "ap-south-1")
        if api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
        )
    except Exception:
        return None


def _has_key() -> bool:
    try:
        k = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        return bool(k and k.strip())
    except Exception:
        return False


# ── System prompt ─────────────────────────────────────────────────────────────
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
4. If zero statutory text was supplied: write Block 1 saying so, skip Block 2, write Block 3.
5. Never write Block 3 before Block 2 is complete."""


# ── Streaming ─────────────────────────────────────────────────────────────────
def _stream(messages: list[dict], system: str):
    client = get_bedrock_client()
    if not client:
        yield "⚠️ Could not initialise Bedrock client. Check your secrets."
        return
    if not _has_key():
        yield "⚠️ Add **AWS_BEARER_TOKEN_BEDROCK** and **AWS_REGION** in *App → Settings → Secrets*."
        return

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
        "temperature": 0.15,
    })

    try:
        resp = client.invoke_model_with_response_stream(
            modelId=MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        for event in resp.get("body", []):
            chunk = event.get("chunk")
            if not chunk:
                continue
            payload = json.loads(chunk["bytes"].decode())
            if payload.get("type") == "content_block_delta":
                delta = payload.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield text
    except Exception as e:
        yield f"\n\n⚠️ Bedrock error: {e}"


# ── Helpers ───────────────────────────────────────────────────────────────────
def build_prompt(query: str, all_results: dict) -> str:
    grounding = corpus.render_all_results(all_results)
    no_prov   = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
    parts = [f"=== STATUTORY TEXT ===\n{grounding}"]
    if no_prov:
        parts.append(
            "=== NO PROVISION FOUND IN THESE CODES ===\n"
            + "\n".join(f"• {n}" for n in no_prov)
            + "\n(State this explicitly in your answer for each.)"
        )
    parts.append(f"=== QUESTION ===\n{query}")
    return "\n\n".join(parts)


def _correction_html(corrections):
    pairs = ", ".join(
        f'<strong>{o}</strong> → <strong>{f}</strong>'
        for o, f in corrections
    )
    return f'<div class="lc-correction">✏️&nbsp; Interpreted as: {pairs}</div>'


def _src_row(sources, no_provision):
    src_html  = "".join(f'<span class="lc-src-chip">📋 {s}</span>'  for s in sources)
    none_html = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in no_provision)
    return (
        f'<div class="lc-src-row">'
        f'<span class="lc-src-label">Sources</span>'
        f'{src_html}{none_html}'
        f'</div>'
    )


# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []
if "pending" not in st.session_state:
    st.session_state.pending: str | None = None


def _submit(q: str):
    st.session_state.pending = q


# ══ HERO ══════════════════════════════════════════════════════════════════════
chips = "".join(
    f'<span class="lc-code-chip">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)
st.markdown(f"""
<div class="lc-hero">
  <div class="lc-eyebrow"><span class="lc-dot"></span>Indian Labour Codes · Legal Reference</div>
  <h1 class="lc-title">Labour Codes <em>Assistant</em></h1>
  <p class="lc-sub">Every answer grounded in the four Labour Codes and their Central Rules —
  precise Section and Rule citations, every time.</p>
  <div class="lc-codes">{chips}</div>
</div>
""", unsafe_allow_html=True)

if not _has_key():
    st.markdown(
        '<div class="lc-alert">⚙️&nbsp; Add <strong>AWS_BEARER_TOKEN_BEDROCK</strong> '
        'and <strong>AWS_REGION</strong> in <em>App → Settings → Secrets</em> to activate.</div>',
        unsafe_allow_html=True,
    )

# ── Chat input ─────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask anything — e.g. What are the conditions for retrenchment?"):
    _submit(prompt)

# ── History ────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="⚖️"):
            if msg.get("corrections"):
                st.markdown(_correction_html(msg["corrections"]), unsafe_allow_html=True)
            if msg.get("sources") or msg.get("no_provision"):
                st.markdown(_src_row(msg.get("sources", []), msg.get("no_provision", [])), unsafe_allow_html=True)
            st.markdown(msg["content"])

# ── Sample questions ───────────────────────────────────────────────────────────
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
        (c1 if i % 2 == 0 else c2).button(s, key=f"s{i}", on_click=_submit, args=(s,))

# ── Process ────────────────────────────────────────────────────────────────────
if st.session_state.pending:
    raw_q = st.session_state.pending
    st.session_state.pending = None

    corrected_q, corrections = corpus.correct_query(raw_q)

    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    with st.spinner("Searching the codes…"):
        all_results  = corpus.search_all(LOADED, corrected_q, k=4)

    sources      = [r["meta"]["short"] for r in all_results.values() if r["found"]]
    no_provision = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
    user_msg     = build_prompt(corrected_q, all_results)

    with st.chat_message("assistant", avatar="⚖️"):
        if corrections:
            st.markdown(_correction_html(corrections), unsafe_allow_html=True)
        if sources or no_provision:
            st.markdown(_src_row(sources, no_provision), unsafe_allow_html=True)

        if not sources:
            names    = " · ".join(e["meta"]["short"] for e in LOADED.values())
            response = (
                f"No relevant provisions were found across **{names}** for this query. "
                "Please try rephrasing, or ask about a specific Section or topic."
            )
            st.markdown(response)
        else:
            response = st.write_stream(
                _stream([{"role": "user", "content": user_msg}], system=SYSTEM)
            )

    st.session_state.messages.append({
        "role":         "assistant",
        "content":      response,
        "sources":      sources,
        "no_provision": no_provision,
        "corrections":  corrections,
    })
    st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="lc-footer">'
    'Legal reference for HR &amp; Legal teams'
    '<span>·</span>'
    'Claude Sonnet 4.6 via AWS Bedrock'
    '<span>·</span>'
    'Cited statutory provisions are authoritative'
    '</div>',
    unsafe_allow_html=True,
)
