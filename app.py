"""
app.py — Labour Codes Assistant (Streamlit).

Pipeline per question:
  1) ROUTE  (Gemini): decide which code, or ask "which code?" when a term is
            defined differently across codes (e.g. "wages").
  2) RETRIEVE (local): pull only the relevant Sections/Rules from that code.
  3) ANSWER (Gemini): answer strictly from those slices, citing exact Section/Rule.

Keys live in st.secrets (server-side) and are rotated automatically. End users
just type — no key, no setup.
"""
import itertools
import json
import threading

import requests
import streamlit as st

import corpus

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

st.set_page_config(page_title="Labour Codes Assistant", page_icon="§", layout="centered")

st.markdown("""
<style>
  .stApp { background:#f5f1e8; }
  h1,h2,h3 { font-family:Georgia,'Times New Roman',serif; letter-spacing:.2px; }
  .lc-title { font-family:Georgia,serif; font-size:30px; font-weight:600; color:#26201a; margin:0; }
  .lc-sub { color:#6b5d4d; font-style:italic; margin:.15rem 0 0; font-size:15px; }
  .lc-seal { display:inline-grid; place-items:center; width:42px; height:42px; border:1.5px solid #9a7b3f;
             border-radius:50%; color:#9a7b3f; font:600 20px Georgia,serif; margin-right:10px; vertical-align:middle; }
  .lc-src { color:#7c2b2b; font-size:13px; font-weight:600; margin-bottom:.3rem; }
  .lc-note { color:#6b5d4d; font-size:12.5px; font-style:italic; border-top:1px dashed #cfc3ad;
             padding-top:6px; margin-top:10px; }
  .stChatMessage strong { color:#7c2b2b; }   /* citations stand out */
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- resources
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()


@st.cache_resource
def get_pool():
    raw = st.secrets.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in (raw if isinstance(raw, str) else ",".join(raw)).split(",") if k.strip()]
    return {"keys": keys, "cycle": itertools.cycle(keys) if keys else None, "lock": threading.Lock()}


CFG, CORPUS = get_corpus()
POOL = get_pool()
MODEL = CFG.get("model", "gemini-2.5-flash")
LOADED = {cid: e for cid, e in CORPUS.items()}


def gemini(system, contents, want_json=False, temperature=0.2):
    if not POOL["keys"]:
        raise RuntimeError("No API keys configured. Add GEMINI_API_KEYS in app Secrets.")
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


ROUTER_SYSTEM = f"""You route questions for an assistant covering ONLY these Indian labour codes \
(and their Central Rules) that are currently loaded:
{{scope}}

Using the latest user message and the conversation, return ONLY JSON:
{{{{"mode":"answer"|"clarify","codes":[...],"message":"..."}}}}

- "answer": the question clearly concerns one loaded code, OR the user is replying to an earlier
  clarification by naming a code, OR they explicitly want a comparison (list all relevant ids).
  Leave "message" empty.
- "clarify": a term/topic is defined or treated differently across more than one loaded code and the
  user hasn't said which (e.g. "wages", "employee", "worker", "appropriate Government", "establishment").
  Put the candidate ids in "codes" and a short, polite question naming those codes in "message".
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
Keep it well-organised and no longer than needed."""


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
        sel = corpus.search(LOADED[cid], query, k=12)
        picks += sel
        sources.append(LOADED[cid]["meta"]["title"])
    grounding = corpus.render_chunks(picks)
    contents = [{"role": "user", "parts": [{"text": "Use only the following statutory text:\n\n" + grounding}]},
                {"role": "model", "parts": [{"text": "Understood. I will answer strictly from this text "
                 "and cite exact Sections and Rules."}]}] + to_contents(history)
    answer = gemini(ANSWER_SYSTEM, contents, temperature=0.2)
    return {"kind": "answer", "content": answer, "sources": sources}


# ----------------------------------------------------------------- UI state
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.last_query = None
    st.session_state.todo = None

st.markdown('<div><span class="lc-seal">§</span>'
            '<span class="lc-title">Labour Codes Assistant</span></div>'
            '<p class="lc-sub">Grounded only in the Codes and their Central Rules · internal reference</p>',
            unsafe_allow_html=True)

if not POOL["keys"]:
    st.warning("No API keys set yet. Add **GEMINI_API_KEYS** (comma-separated) in the app's Secrets.")
if not LOADED:
    st.warning("No code documents loaded. Put the PDFs in documents/pdfs/, run `python ingest.py`, redeploy.")
else:
    st.caption("Loaded: " + " · ".join(e["meta"]["short"] for e in LOADED.values()))


def choose(code_id, label):
    st.session_state.messages.append({"role": "user", "kind": "text", "content": f"I mean the {label}."})
    st.session_state.todo = (st.session_state.last_query, code_id)


# input
if prompt := st.chat_input("e.g. What is the definition of wages?"):
    st.session_state.messages.append({"role": "user", "kind": "text", "content": prompt})
    st.session_state.last_query = prompt
    st.session_state.todo = (prompt, None)

# process any queued work (from input or a clarify button)
if st.session_state.todo:
    q, fc = st.session_state.todo
    st.session_state.todo = None
    hist = [m for m in st.session_state.messages if m["kind"] in ("text",)]
    with st.spinner("Reading the code…"):
        try:
            res = run_pipeline(hist, forced_code=fc)
        except Exception as e:
            res = {"kind": "answer", "content": f"Sorry — {e}", "sources": []}
    msg = {"role": "assistant", **res}
    if res["kind"] == "answer":
        msg["kind"] = "text"
    st.session_state.messages.append(msg)

# render
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"], avatar=("§" if m["role"] == "assistant" else None)):
        if m.get("kind") == "clarify":
            st.markdown(m["content"])
            last = (i == len(st.session_state.messages) - 1)
            cols = st.columns(max(len(m.get("options", [])), 1))
            for col, opt in zip(cols, m.get("options", [])):
                col.button(opt["label"], key=f"opt-{i}-{opt['id']}", disabled=not last,
                           on_click=choose, args=(opt["id"], opt["label"]))
        else:
            if m["role"] == "assistant" and m.get("sources"):
                st.markdown(f'<div class="lc-src">Source: {" · ".join(m["sources"])}</div>',
                            unsafe_allow_html=True)
            st.markdown(m["content"])

if not st.session_state.messages:
    st.info("Ask about any provision in the loaded codes. I answer only from the statutory text and "
            "cite the exact Section and Rule. If a term differs across codes — like *wages* — I'll first "
            "ask which one you mean.")
