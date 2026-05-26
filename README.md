# Labour Codes Assistant

A private chat tool for HR that answers **only** from the four Indian labour Codes
and their Central Rules. It cites the exact Section/Rule every time, refuses outside
knowledge, and asks **which code** when a term (e.g. "wages") differs across codes.
End users open one link and type — no key, no setup for them.

## How it works
1. **Route** (Gemini) — picks the relevant code, or asks "which code?" when ambiguous.
2. **Retrieve** (local Python) — pulls only the relevant Sections/Rules from that code,
   so every question stays small and fast no matter how large the source is.
3. **Answer** (Gemini) — answers strictly from those slices, citing exact Sections/Rules.

Your Gemini keys live in Streamlit **Secrets** (server-side) and are rotated automatically.

## What's already done
Three codes are processed and built in: **Code on Wages 2019**, **Industrial Relations
Code 2020**, **Code on Social Security 2020**. The app runs on whatever is loaded.

## Add the rest (5 PDFs)
Drop these into `documents/pdfs/` and run `python ingest.py`:
OSH & WC Code 2020, and the four Central Rules (Wages, IR, Social Security, OSH).
Filenames are matched by keyword, so exact names aren't needed.

## Deploy (one-time)
1. Create a **private** GitHub repo and push this folder.
2. Go to share.streamlit.io → "New app" → pick the repo → main file `app.py` → Deploy.
3. App → Settings → **Secrets**, paste (comma-separate as many keys as you have):
   ```
   GEMINI_API_KEYS = "key1,key2,key3"
   ```
   Free keys (no card): https://aistudio.google.com/apikey
4. App → **Share** → add your HR team's email addresses as viewers. Because the repo is
   private, only people you invite can open the link.

Update later (e.g. add the "old Acts → what changed" feature, or new rules): push to the
repo and Streamlit redeploys automatically.

## Run locally (optional)
```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your keys
streamlit run app.py
```

## Note
Informational reference for HR. The cited provision in the Code or Rules is the
authoritative text; for a contested interpretation, consult a qualified professional.
For sensitive queries, use a **paid** Gemini key (the free tier may use prompts for training).
```
