# Labour Codes Assistant

A private chat tool for HR that answers **only** from the four Indian labour Codes
and their Central Rules. It cites the exact Section/Rule every time, refuses outside
knowledge, and asks **which code** when a term (e.g. "wages") differs across codes.
End users open one link and type — no key, no setup for them.

## How it works
1. **Clarify** (Claude) — asks one short "which code?"-style question only when the
   query is ambiguous; otherwise answers straight away.
2. **Retrieve** (local Python) — pulls only the relevant Sections/Rules from across the
   four codes, so every question stays small and fast no matter how large the source is.
3. **Answer** (Claude) — answers strictly from those slices, citing exact Sections/Rules.

The model is **Claude Sonnet 4.6 on AWS Bedrock**. Your Bedrock API key lives in
Streamlit **Secrets** (server-side); end users never see or need it.

## What's already done
Three codes are processed and built in: **Code on Wages 2019**, **Industrial Relations
Code 2020**, **Code on Social Security 2020**. The app runs on whatever is loaded.

## Add the rest (5 PDFs)
Drop these into `documents/pdfs/` and run `python ingest.py`:
OSH & WC Code 2020, and the four Central Rules (Wages, IR, Social Security, OSH).
Filenames are matched by keyword, so exact names aren't needed.

## One-time AWS Bedrock setup
Claude on Bedrock needs a **paid AWS account** (a valid card on file). There is no longer
a "Model access" button — AWS enables foundation models by default — so instead:
1. **Billing → Payment preferences** — add a valid card.
2. **Amazon Bedrock → Playground**, region **Asia Pacific (Mumbai) `ap-south-1`** → pick
   **Claude Sonnet 4.6** → submit the one-time **use-case form** → send a test message.
   That first call creates the AWS Marketplace subscription for the model.
3. **Bedrock → API keys** → create a long-term key to use as `AWS_BEARER_TOKEN_BEDROCK`.
   The key's identity needs `bedrock:InvokeModel*` plus `aws-marketplace:Subscribe` and
   `aws-marketplace:ViewSubscriptions`.

> Mumbai reaches Claude only through the **global** inference profile
> (`global.anthropic.claude-sonnet-4-6`), which is already the default in `app.py`.

## Deploy (one-time)
1. Create a **private** GitHub repo and push this folder.
2. Go to share.streamlit.io → "New app" → pick the repo → main file `app.py` → Deploy.
3. App → Settings → **Secrets**, paste:
   ```
   AWS_BEARER_TOKEN_BEDROCK = "your-bedrock-api-key"
   AWS_REGION = "ap-south-1"
   # optional — overrides the default model:
   # BEDROCK_MODEL_ID = "global.anthropic.claude-sonnet-4-6"
   ```
4. App → **Share** → add your HR team's email addresses as viewers. Because the repo is
   private, only people you invite can open the link.

Update later (e.g. add the "old Acts → what changed" feature, or new rules): push to the
repo and Streamlit redeploys automatically.

## Run locally (optional)
```
pip install -r requirements.txt
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'EOF'
AWS_BEARER_TOKEN_BEDROCK = "your-bedrock-api-key"
AWS_REGION = "ap-south-1"
EOF
streamlit run app.py
```

## Note
Informational reference for HR. The cited provision in the Code or Rules is the
authoritative text; for a contested interpretation, consult a qualified professional.
Bedrock usage is billed per token to your AWS account.
