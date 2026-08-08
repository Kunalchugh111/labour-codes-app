# Labour Codes Assistant

A private chat tool for HR that answers **only** from the four Indian labour Codes
and their Central Rules. It cites the exact Section/Rule every time, refuses outside
knowledge, and asks **which code** when a term (e.g. "wages") differs across codes.
End users open one link and type — no key, no setup for them.

## How it works
1. **Expand** (LLM) — rewrites your plain-English question or situation into the statute's own
   legal terms, so the search finds the right provisions even when you don't use legal words.
2. **Retrieve** (local Python) — pulls only the relevant Sections/Rules from across the four
   codes, so every question stays small and fast no matter how large the source is.
3. **Dissect & answer** (LLM) — breaks your situation into the distinct legal issues it raises,
   grounds each issue in the governing Section/Rule, applies the law to your facts, then gives a
   verdict and next steps — strictly from those slices, citing exact Sections/Rules.

The model is **Amazon Nova Pro on AWS Bedrock**, called through the model-agnostic **Converse
API** — switch to any other Bedrock model with one secret (`BEDROCK_MODEL_ID`); a stronger model
(e.g. a Claude model) sharpens the issue-by-issue reasoning. Your Bedrock API key lives in
Streamlit **Secrets** (server-side); end users never see or need it.

## What's already done
All four Codes — **Code on Wages 2019**, **Industrial Relations Code 2020**, **Code on
Social Security 2020**, **OSH & WC Code 2020** — plus their **2026 Central Rules** and the
repealed Acts they replaced are processed and built in.

## Re-ingesting PDFs
Drop official PDFs into `documents/pdfs/` and run `python ingest.py` (uses PyMuPDF).
The Central Rules ship as **bilingual Gazette PDFs** (English + Hindi pages); ingestion
keeps the **English pages only**, so the processed text is clean English. Filenames are
matched by keyword, so exact names aren't needed.

## One-time AWS Bedrock setup
Bedrock needs a **paid AWS account** (a valid card on file). Amazon Nova is a
**first-party model**, so — unlike Anthropic Claude — it needs **no Marketplace
subscription and no use-case form**. Just:
1. **Billing → Payment preferences** — add a valid card.
2. **Bedrock → API keys** → create a long-term key to use as `AWS_BEARER_TOKEN_BEDROCK`.
   Its identity needs the `bedrock:InvokeModel` permission.
3. Pick a region where **Nova Pro** is offered — it is **not** available in Mumbai
   (`ap-south-1`). Closest to India is **`ap-southeast-3` (Jakarta)**; **`us-east-1`** has
   the most capacity. Use that as your `AWS_REGION` secret.

## Deploy (one-time)
1. Create a **private** GitHub repo and push this folder.
2. Go to share.streamlit.io → "New app" → pick the repo → main file `app.py` → Deploy.
3. App → Settings → **Secrets**, paste:
   ```
   AWS_BEARER_TOKEN_BEDROCK = "your-bedrock-api-key"
   AWS_REGION = "us-east-1"        # or ap-southeast-3 (Jakarta) — NOT ap-south-1
   # optional — use a different Bedrock model:
   # BEDROCK_MODEL_ID = "amazon.nova-pro-v1:0"
   ```
4. App → **Share** → add your HR team's email addresses as viewers. Because the repo is
   private, only people you invite can open the link.

Update later (e.g. add the "old Acts → what changed" feature, or new rules): push to the
repo and Streamlit redeploys automatically.

## Sign-in & usage tracking (optional)
Add a `[users]` table to the same **Secrets** to require sign-in — including for people
outside the company: create a login (a plain username **or their email address**), tell
them the password, and they sign in on the app's gate screen. Every login, logout, failed
sign-in and question is recorded, and admins get a **📊 Usage & activity** panel (per-user
question counts, login history, recent questions) with **CSV report downloads**:

```
admins = ["rohit"]                        # usernames who can open the usage panel

[users]
rohit = "some-password"                   # plaintext…
priya = "d74ff0ee8da3b98065b0..."         # …or a sha256 hex digest of the password
                                          #   python3 -c "import hashlib;print(hashlib.sha256(b'pw').hexdigest())"
"vendor@theircompany.com" = "invite-pw"   # email logins MUST be quoted (the @ and dots)
```

- **Email keys must be in quotes** — an unquoted `a@b.com = "pw"` is invalid TOML-table
  syntax and that entry is ignored. Sign-in matches usernames/emails case-insensitively
  and ignores stray spaces.
- **No `[users]` table → no sign-in** — the app runs open, questions are logged as `anonymous`.
- Signed-in users see their own name + question count in the header, with a **Sign out** button.
- Admins can download **`usage-summary-<date>.csv`** (per-user totals) and
  **`usage-activity-<date>.csv`** (every event with question text) from the panel — both
  open directly in Excel.
- The log is a local SQLite file (`usage.db`, gitignored). On Streamlit Community Cloud the
  filesystem is **ephemeral**: history survives reruns/restarts but a **redeploy resets it** —
  download the CSVs before redeploying, or point the optional `USAGE_DB` secret at a
  persistent path.

## Run locally (optional)
```
pip install -r requirements.txt
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'EOF'
AWS_BEARER_TOKEN_BEDROCK = "your-bedrock-api-key"
AWS_REGION = "us-east-1"
EOF
streamlit run app.py
```

## Switching models
The app uses the Bedrock **Converse API**, which is identical across models. To try a
different one (e.g. a Claude or Llama model once you have access), set the
`BEDROCK_MODEL_ID` secret to that model's ID and make sure `AWS_REGION` is a region where
it's available — no code change needed.

## Preview the answer layout
Append `?demo=1` to the app URL to see sample answers rendered in the current card layout
(restatement, verdict card, the issue-by-issue **Analysis**, action box, citation pills,
collapsible statutory text) — no Bedrock key needed. Handy for checking the look after a change.

## Note
Informational reference for HR. The cited provision in the Code or Rules is the
authoritative text; for a contested interpretation, consult a qualified professional.
Bedrock usage is billed per token to your AWS account.
