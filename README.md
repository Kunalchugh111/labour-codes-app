# Labour Codes Assistant

A private chat tool for HR that answers **only** from the four Indian labour Codes
and their Central Rules. It cites the exact Section/Rule every time, refuses outside
knowledge, and asks **which code** when a term (e.g. "wages") differs across codes.
End users open one link and type — no key, no setup for them.

## How it works
1. **Clarify** (LLM) — asks one short "which code?"-style question only when the
   query is ambiguous; otherwise answers straight away.
2. **Retrieve** (local Python) — pulls only the relevant Sections/Rules from across the
   four codes, so every question stays small and fast no matter how large the source is.
3. **Answer** (LLM) — answers strictly from those slices, citing exact Sections/Rules.

The model is **Amazon Nova Pro on AWS Bedrock**, called through the model-agnostic
**Converse API** — so you can switch to any other Bedrock model by setting one secret
(`BEDROCK_MODEL_ID`). Your Bedrock API key lives in Streamlit **Secrets** (server-side);
end users never see or need it.

## What's already done
Three codes are processed and built in: **Code on Wages 2019**, **Industrial Relations
Code 2020**, **Code on Social Security 2020**. The app runs on whatever is loaded.

## Add the rest (5 PDFs)
Drop these into `documents/pdfs/` and run `python ingest.py`:
OSH & WC Code 2020, and the four Central Rules (Wages, IR, Social Security, OSH).
Filenames are matched by keyword, so exact names aren't needed.

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
(verdict card, requirements checklist, action box, citation pills, collapsible statutory text)
— no Bedrock key needed. Handy for checking the look after a change.

## Note
Informational reference for HR. The cited provision in the Code or Rules is the
authoritative text; for a contested interpretation, consult a qualified professional.
Bedrock usage is billed per token to your AWS account.
