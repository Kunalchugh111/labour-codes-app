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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');

:root{
  --bg1:#16120e; --bg2:#1e1813; --card:#221b14; --line:rgba(201,162,94,.20);
  --gold:#c9a25e; --gold2:#e2c489; --txt:#efe7d8; --muted:#a59a87;
}
.stApp{
  background:radial-gradient(1100px 600px at 50% -8%, #241d15 0%, var(--bg1) 55%) fixed;
  color:var(--txt); font-family:'Plus Jakarta Sans',system-ui,sans-serif;
}
/* hide default chrome for an app-like feel */
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important;}
.block-container{max-width:820px;padding-top:2.2rem!important;padding-bottom:6rem;}
h1,h2,h3,h4{font-family:'Fraunces',Georgia,serif;color:var(--txt);}

/* hero */
.lc-hero{text-align:center;margin:.2rem 0 1.4rem;}
.lc-seal{display:inline-grid;place-items:center;width:64px;height:64px;border-radius:50%;
  border:1.6px solid var(--gold);color:var(--gold);font:600 30px 'Fraunces',serif;
  box-shadow:0 0 0 6px rgba(201,162,94,.06),0 14px 40px -18px rgba(0,0,0,.8);margin-bottom:14px;}
.lc-title{font-family:'Fraunces',serif;font-weight:600;font-size:38px;line-height:1.05;margin:0;
  background:linear-gradient(180deg,#f6efe0,#cdb486);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;letter-spacing:.3px;}
.lc-sub{color:var(--muted);font-size:15px;margin:.5rem auto 0;max-width:520px;line-height:1.5;}
.lc-rule{height:1px;background:linear-gradient(90deg,transparent,var(--line),transparent);margin:1.3rem 0;}
.lc-badges{display:flex;flex-wrap:wrap;gap:7px;justify-content:center;margin-top:14px;}
.lc-badge{font-size:12px;color:var(--gold2);border:1px solid var(--line);background:rgba(201,162,94,.06);
  padding:4px 11px;border-radius:999px;letter-spacing:.2px;}
.lc-eyebrow{color:var(--muted);font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;
  text-align:center;margin:.3rem 0 .7rem;}

/* notices */
.lc-warn{border:1px solid var(--line);background:rgba(201,162,94,.07);border-radius:12px;
  padding:12px 16px;color:var(--gold2);font-size:14px;text-align:center;margin-bottom:6px;}

/* chat */
[data-testid="stChatMessage"]{background:transparent;border:none;padding:.15rem 0;}
[data-testid="stChatMessageContent"]{font-size:15.5px;line-height:1.65;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){
  background:var(--card);border:1px solid var(--line);border-left:3px solid var(--gold);
  border-radius:14px;padding:14px 18px;box-shadow:0 18px 50px -34px rgba(0,0,0,.9);}
[data-testid="stChatMessageContent"] strong{color:var(--gold2);font-weight:600;}
.lc-src{color:var(--gold);font-size:12px;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase;margin-bottom:7px;}

/* buttons / chips */
.stButton>button{background:rgba(201,162,94,.08);color:var(--gold2);border:1px solid var(--line);
  border-radius:11px;padding:9px 14px;font-size:14px;font-weight:500;transition:.16s;width:100%;
  text-align:left;line-height:1.35;}
.stButton>button:hover{background:var(--gold);color:#1a140d;border-color:var(--gold);transform:translateY(-1px);}

/* chat input */
[data-testid="stChatInput"]{background:var(--card);border:1px solid var(--line);border-radius:14px;}
[data-testid="stChatInput"] textarea{color:var(--txt)!important;font-size:15.5px;}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted);}
[data-testid="stBottomBlockContainer"]{background:transparent;}
.lc-foot{color:var(--muted);font-size:11.5px;text-align:center;font-style:italic;margin-top:.6rem;}
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

Using the latest user message and the conversation, return ONLY JSON:
{{"mode":"answer"|"clarify","codes":[...],"message":"..."}}

- "answer": the question clearly concerns one loaded code, OR the user is replying to an earlier
  clarification by naming a code, OR they explicitly want a comparison (list all relevant ids).
  Leave "message" empty.
- "clarify": a term/topic is defined or treated differently across more than one loaded code and the
  user hasn't said which (e.g. "wages", "employee", "worker", "appropriate Government", "establishment").
  Put candidate ids in "codes" and a short, polite question naming those codes in "message".
- "answer" with empty "codes": clearly outside all loaded codes.
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
        try:
            route = json.loads(gemini(ROUTER_SYSTEM.format(scope=scope_lines()),
                                      to_contents(history), want_json=True, temperature=0.0))
        except Exception:
            route = {"mode": "answer", "codes": list(LOADED)[:1]}
        if route.get("mode") == "clarify":
            opts = [{"id": cid, "label": LOADED[cid]["meta"]["short"]}
                    for cid in route.get("codes", []) if cid in LOADED]
            return {"kind": "clarify", "content": route.get("message", "Which code do you mean?"),
                    "options": opts}
        codes = [c for c in route.get("codes", []) if c in LOADED]

    if not codes:
        return {"kind": "answer", "content": "That question doesn't appear to fall within the labour "
                "codes loaded here. I can only answer from those codes and their Central Rules.",
                "sources": []}

    query = history[-1]["content"]
    picks, sources = [], []
    for cid in codes:
        picks += corpus.search(LOADED[cid], query, k=12)
        sources.append(LOADED[cid]["meta"]["title"])
    grounding = corpus.render_chunks(picks)
    contents = [{"role": "user", "parts": [{"text": "Use only the following statutory text:\n\n" + grounding}]},
                {"role": "model", "parts": [{"text": "Understood. I will answer strictly from this text "
                 "and cite exact Sections and Rules."}]}] + to_contents(history)
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
  <div class="lc-seal">§</div>
  <div class="lc-title">Labour Codes Assistant</div>
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
        with st.chat_message(m["role"], avatar=("§" if m["role"] == "assistant" else "🧑")):
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
