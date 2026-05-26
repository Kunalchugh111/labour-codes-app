"""
app.py — Labour Codes Assistant (Streamlit).

Pipeline per question:
  1) ROUTE  (Gemini): decide which code, or ask "which code?" when a term is
            defined differently across codes (e.g. "wages").
  2) RETRIEVE (local): pull only the relevant Sections/Rules from that code.
  3) ANSWER (Gemini): answer strictly from those slices, citing exact Section/Rule.

Keys live in st.secrets (server-side) and are rotated automatically.
"""
import itertools
import json
import threading

import requests
import streamlit as st

import corpus

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

st.set_page_config(page_title="Labour Codes Assistant", page_icon="§", layout="centered")

# ----------------------------------------------------------------- styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#fafafa;
  --card:#ffffff;
  --border:#e2e8f0;
  --text:#0f172a;
  --muted:#64748b;
  --accent:#2563eb;
  --accent-soft:#eff6ff;
}
.stApp{
  background:var(--bg);
  color:var(--text);
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;
}
/* hide default chrome */
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important;}
.block-container{max-width:760px;padding-top:3rem!important;padding-bottom:6rem;}
h1,h2,h3,h4{color:var(--text);font-family:'Inter',sans-serif;letter-spacing:-0.02em;}

/* hero */
.lc-hero{text-align:left;margin:0 0 1.5rem;}
.lc-title{
  font-size:30px;
  font-weight:700;
  color:var(--text);
  margin:0 0 0.5rem;
  letter-spacing:-0.025em;
  line-height:1.2;
}
.lc-sub{
  color:var(--muted);
  font-size:15px;
  margin:0;
  max-width:560px;
  line-height:1.55;
}
.lc-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:1.25rem;}
.lc-badge{
  font-size:12px;
  font-weight:500;
  color:var(--muted);
  background:var(--card);
  border:1px solid var(--border);
  padding:4px 10px;
  border-radius:6px;
  letter-spacing:0;
}
.lc-rule{height:1px;background:var(--border);margin:1.5rem 0;}
.lc-eyebrow{
  color:var(--muted);
  font-size:13px;
  font-weight:500;
  margin:0.5rem 0 0.75rem;
  letter-spacing:0;
  text-transform:none;
  text-align:left;
}

/* notices */
.lc-warn{
  border:1px solid var(--border);
  background:var(--accent-soft);
  border-radius:8px;
  padding:12px 16px;
  color:var(--text);
  font-size:14px;
  text-align:left;
  margin-bottom:1rem;
}

/* chat */
[data-testid="stChatMessage"]{background:transparent;border:none;padding:0.5rem 0;}
[data-testid="stChatMessageContent"]{font-size:15px;line-height:1.6;color:var(--text);}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){
  background:var(--card);
  border:1px solid var(--border);
  border-radius:10px;
  padding:14px 18px;
}
[data-testid="stChatMessageContent"] strong{color:var(--text);font-weight:600;}
.lc-src{
  color:var(--muted);
  font-size:12px;
  font-weight:500;
  letter-spacing:0;
  text-transform:none;
  margin-bottom:6px;
}

/* buttons / chips */
.stButton>button{
  background:var(--card);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:8px;
  padding:10px 14px;
  font-size:14px;
  font-weight:500;
  transition:0.15s ease;
  width:100%;
  text-align:left;
  line-height:1.4;
}
.stButton>button:hover{
  background:var(--accent-soft);
  color:var(--accent);
  border-color:var(--accent);
}

/* chat input */
[data-testid="stChatInput"]{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:10px;
}
[data-testid="stChatInput"] textarea{color:var(--text)!important;font-size:15px;}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted);}
[data-testid="stBottomBlockContainer"]{background:var(--bg);}
.lc-foot{
  color:var(--muted);
  font-size:12px;
  text-align:center;
  font-style:normal;
  margin-top:1rem;
}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- resources
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()


@st.cache_resource
def get_pool():
    raw = st.secrets.get("GEMINI_API_KEYS", "") if hasattr(st, "secrets") else ""
    try:
        raw = st.secrets.get("GEMINI_API_KEYS", "")
    except Exception:
        raw = ""
    keys = [k.strip() for k in (raw if isinstance(raw, str) else ",".join(raw)).split(",") if k.strip()]
    return {"keys": keys, "cycle": itertools.cycle(keys) if keys else None, "lock": threading.Lock()}


CFG, CORPUS = get_corpus()
POOL = get_pool()
MODEL = CFG.get("model", "gemini-2.5-flash")
LOADED = {cid: e for cid, e in CORPUS.items()}


def gemini(system, contents, want_json=False, temperature=0.2):
    if not POOL["keys"]:
        raise RuntimeError("No API keys configured yet. Add GEMINI_API_KEYS in the app's Secrets.")
    body = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048,
                                 **({"responseMimeType": "application/json"} if want_json else {})}}
    last = None
    for _ in range(len(POOL["keys"])):
        with POOL["lock"]:
            key = next(POOL["cycle"])
        try:
            r = requests.post(f"{API_ROOT}/{MODEL}:generateContent?key={key}", json=body, timeout=90)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"; continue
            r.raise_for_status()
            d = r.json()
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]).strip()
        except requests.RequestException as e:
            last = str(e); continue
    raise RuntimeError(f"All keys failed ({last}).")


# ----------------------------------------------------------------- prompts
def scope_lines():
    return "\n".join(f'- id "{e["meta"]["id"]}": {e["meta"]["title"]} — {e["meta"]["scope"]}'
                     for e in LOADED.values())


ROUTER_SYSTEM = """You route questions for an assistant covering ONLY these Indian labour codes \
(and their Central Rules) that are currently loaded:
{scope}

Route the latest user message on its own merits. Earlier turns are NOT context — do not infer
the topic from them. Return ONLY JSON:
{{"mode":"answer"|"clarify","codes":[...],"message":"..."}}

Keyword hints (use these when the latest message matches; do NOT inherit a code from earlier turns):
- strike, lock-out, trade union, industrial dispute, retrenchment, lay-off, standing orders, closure,
  works committee, grievance redressal, negotiating union → "ir"
- provident fund, PF, EPF, ESI, employees' state insurance, gratuity, pension, maternity benefit,
  employees' compensation, building & construction workers' cess, gig/platform worker → "ss"
- minimum wages, payment of wages, deduction, equal remuneration, bonus, wage period → "wages"
- factories, working hours, leave, welfare facilities, hazardous, contract labour, inter-state migrant,
  mines, dock, plantation → "osh"

Out-of-scope examples (return mode="answer", codes=[]):
- weather, time of day, today's date, news, sports, generic chitchat
- taxation (GST, income tax, customs), corporate law, criminal law, family law
- meta-questions like "which codes do you cover?", "what can you do?", "who are you?"
- anything that doesn't map to a keyword hint above and isn't clearly about employment, wages,
  working conditions, social security, or industrial relations

- "answer": the latest message clearly concerns one loaded code (use the keyword hints), OR explicitly
  asks for a comparison (list all relevant ids). Leave "message" empty.
- "clarify": a term/topic is defined or treated differently across more than one loaded code and the
  user hasn't said which (e.g. "wages", "employee", "worker", "appropriate Government", "establishment").
  Put candidate ids in "codes" and a short, polite question naming those codes in "message".
- "answer" with empty "codes": clearly outside all loaded codes (use the out-of-scope examples above).
Be decisive; only clarify when the ambiguity genuinely changes the legal answer."""

ANSWER_SYSTEM = """You are a precise legal-reference assistant for HR staff. Answer ONLY from the \
statutory text supplied in this prompt (Sections/Rules of Indian labour codes). Rules:
1. Use only the supplied text. No outside knowledge, repealed Acts, case law, or the internet. If the
   answer is not in the supplied text, say so plainly and name what was searched. Never guess a provision.
2. Cite precisely every time: the exact Section/sub-section/clause with the code's short title and year,
   and for rules the exact Rule number with the Central Rules title (e.g. "Section 2(y), the Code on
   Wages, 2019"). Tell the reader where to look ("see Section ...").
3. Write in formal, precise legal English faithful to the wording. Quote only short defining phrases;
   otherwise paraphrase exactly with the citation.
4. Explain what the provision says; do not advise on a specific dispute or predict an outcome. End with
   one short line that this is an informational reference and the cited provision is authoritative.
5. If text from more than one code is supplied, answer per code under a heading and note differences.
Keep it well-organised and no longer than needed. Use **bold** for the Section/Rule citations."""


def to_contents(history):
    return [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in history if m.get("content")]


# ----------------------------------------------------------------- pipeline
def run_pipeline(history, forced_code=None):
    if forced_code and forced_code in LOADED:
        codes = [forced_code]
    else:
        last_user = next((m for m in reversed(history) if m["role"] == "user"), None)
        router_history = [last_user] if last_user else []
        try:
            route = json.loads(gemini(ROUTER_SYSTEM.format(scope=scope_lines()),
                                      to_contents(router_history), want_json=True, temperature=0.0))
        except Exception:
            route = {"mode": "answer", "codes": list(LOADED)[:1]}
        if route.get("mode") == "clarify":
            opts = [{"id": cid, "label": LOADED[cid]["meta"]["short"]}
                    for cid in route.get("codes", []) if cid in LOADED]
            return {"kind": "clarify", "content": route.get("message", "Which code do you mean?"),
                    "options": opts}
        codes = [c for c in route.get("codes", []) if c in LOADED]

    if not codes:
        loaded_list = ", ".join(LOADED[c]["meta"]["short"] for c in LOADED)
        return {"kind": "answer",
                "content": (f"I can only answer from the loaded labour codes and their Central Rules: "
                            f"**{loaded_list}**. Your question doesn't appear to fall within them — "
                            "please rephrase, or ask about one of these codes."),
                "sources": []}

    query = history[-1]["content"]
    picks, sources = [], []
    for cid in codes:
        chunks = corpus.search(LOADED[cid], query, k=12)
        if chunks:
            picks += chunks
            sources.append(LOADED[cid]["meta"]["title"])

    if not picks:
        other = [cid for cid in LOADED if cid not in codes]
        opts = [{"id": cid, "label": LOADED[cid]["meta"]["short"]} for cid in other]
        chosen = " and ".join(LOADED[c]["meta"]["short"] for c in codes)
        msg = (f"I didn't find anything on that in **{chosen}**. "
               "Would you like me to check another code?")
        return {"kind": "clarify", "content": msg, "options": opts}

    grounding = corpus.render_chunks(picks)
    contents = [{"role": "user", "parts": [{"text": "Use only the following statutory text:\n\n" + grounding}]},
                {"role": "model", "parts": [{"text": "Understood. I will answer strictly from this text "
                 "and cite exact Sections and Rules."}]},
                {"role": "user", "parts": [{"text": query}]}]
    answer = gemini(ANSWER_SYSTEM, contents, temperature=0.2)
    return {"kind": "answer", "content": answer, "sources": sources}


# ----------------------------------------------------------------- state + actions
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.last_query = None
    st.session_state.todo = None


def ask(query, forced_code=None, label=None):
    st.session_state.messages.append({"role": "user", "kind": "text",
                                      "content": label or query})
    if forced_code is None:
        st.session_state.last_query = query
    st.session_state.todo = (query if forced_code is None else st.session_state.last_query, forced_code)


# ----------------------------------------------------------------- header
badges = "".join(f'<span class="lc-badge">{e["meta"]["short"]}</span>' for e in LOADED.values())
st.markdown(f"""
<div class="lc-hero">
  <h1 class="lc-title">Labour Codes Assistant</h1>
  <p class="lc-sub">Answers grounded only in the Codes and their Central Rules, with the exact
  Section and Rule cited every time.</p>
  <div class="lc-badges">{badges}</div>
</div>
<div class="lc-rule"></div>
""", unsafe_allow_html=True)

if not POOL["keys"]:
    st.markdown('<div class="lc-warn">⚙️ Almost there — add your <b>GEMINI_API_KEYS</b> in '
                'App&nbsp;→&nbsp;Settings&nbsp;→&nbsp;Secrets, then it starts answering.</div>',
                unsafe_allow_html=True)

# ----------------------------------------------------------------- input
if prompt := st.chat_input("Ask about any provision…  e.g. What is the definition of wages?"):
    ask(prompt)

# process queued work
if st.session_state.todo:
    q, fc = st.session_state.todo
    st.session_state.todo = None
    hist = [m for m in st.session_state.messages if m["kind"] == "text"]
    with st.spinner("Reading the code…"):
        try:
            res = run_pipeline(hist, forced_code=fc)
        except Exception as e:
            res = {"kind": "answer", "content": f"Sorry — {e}", "sources": []}
    st.session_state.messages.append({"role": "assistant",
                                      "kind": "text" if res["kind"] == "answer" else "clarify", **res})

# ----------------------------------------------------------------- render
if not st.session_state.messages:
    st.markdown('<div class="lc-eyebrow">Try asking</div>', unsafe_allow_html=True)
    samples = ["What is the definition of wages?",
               "How is the minimum rate of wages fixed?",
               "What notice is required before retrenchment?",
               "When is an employee eligible for bonus?"]
    c1, c2 = st.columns(2)
    for i, s in enumerate(samples):
        (c1 if i % 2 == 0 else c2).button(s, key=f"samp{i}", on_click=ask, args=(s,))
else:
    for i, m in enumerate(st.session_state.messages):
        with st.chat_message(m["role"], avatar=("⚖️" if m["role"] == "assistant" else "🧑")):
            if m.get("kind") == "clarify":
                st.markdown(m["content"])
                last = (i == len(st.session_state.messages) - 1)
                cols = st.columns(max(len(m.get("options", [])), 1))
                for col, opt in zip(cols, m.get("options", [])):
                    col.button(opt["label"], key=f"opt-{i}-{opt['id']}", disabled=not last,
                               on_click=ask, args=(st.session_state.last_query, opt["id"],
                                                   f"The {opt['label']}."))
            else:
                if m["role"] == "assistant" and m.get("sources"):
                    st.markdown(f'<div class="lc-src">Source · {" · ".join(m["sources"])}</div>',
                                unsafe_allow_html=True)
                st.markdown(m["content"])

st.markdown('<div class="lc-foot">Informational reference for HR · the cited provision is the '
            'authoritative text</div>', unsafe_allow_html=True)
