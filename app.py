"""
app.py — Labour Codes Assistant (Streamlit)
Backend : AWS Bedrock (Converse API) — amazon.nova-pro-v1:0
Auth    : AWS_BEARER_TOKEN_BEDROCK + AWS_REGION in Streamlit secrets
Design  : Legal editorial — deep navy, parchment, gold accent
"""

import json
import os
import re
import html
import boto3
import streamlit as st

import corpus
import intake

# Amazon Nova Pro — first-party model, no AWS Marketplace subscription required.
# Override with the BEDROCK_MODEL_ID secret to use a different Bedrock model.
MODEL_ID = "amazon.nova-pro-v1:0"

st.set_page_config(
    page_title="Labour Codes Assistant",
    page_icon="⚖️",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — complete ground-up rewrite, every px intentional
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400;1,700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&display=swap');

/* ══ Design Tokens ══════════════════════════════════════════════════════════ */
:root {
  --navy:        #0C1B3A;
  --navy-2:      #142552;
  --navy-3:      #1D3470;
  --navy-4:      #253D8A;
  --gold:        #C9A84C;
  --gold-2:      #E8C97A;
  --gold-pale:   #FBF3DC;
  --gold-border: #E4CE95;
  --parchment:   #F8F6F0;
  --parchment-2: #F2EFE6;
  --parchment-3: #EAE5D8;
  --white:       #FFFFFF;
  --ink:         #0A1525;
  --ink-2:       #1C2D47;
  --slate:       #4A5568;
  --slate-2:     #6B7A8D;
  --slate-3:     #9AA5B4;
  --slate-4:     #C8D0DB;
  --slate-5:     #E4E8EE;
  --green:       #14532D;
  --green-bg:    #F0FBF4;
  --green-b:     #A7F3C2;
  --red:         #7F1D1D;
  --red-bg:      #FFF5F5;
  --red-b:       #FECACA;
  --amber:       #78350F;
  --amber-bg:    #FFFBF0;
  --amber-b:     #FDE68A;

  --ease:        cubic-bezier(0.22, 1, 0.36, 1);
  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);

  --s1: 0 1px 4px rgba(12,27,58,.07);
  --s2: 0 4px 20px rgba(12,27,58,.10);
  --s3: 0 12px 40px rgba(12,27,58,.14);
  --s4: 0 24px 60px rgba(12,27,58,.18);
  --s-gold: 0 4px 24px rgba(201,168,76,.25);
}

/* ══ Global Reset ═══════════════════════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

html, body, .stApp {
  background: var(--parchment) !important;
  font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ── Kill every piece of Streamlit chrome ─────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu, footer { display: none !important; }

/* ── Main content column ─────────────────────────────────────────────────── */
.main .block-container {
  max-width: 820px !important;
  padding: 0 1.5rem 9rem !important;
  margin: 0 auto !important;
}

/* ══ CRITICAL: Fix the black bar at bottom ════════════════════════════════
   Root cause: Streamlit's stBottom uses a pseudo-element or child div that
   inherits a dark background from the app shell. We must override EVERY layer.
   ═════════════════════════════════════════════════════════════════════════ */
[data-testid="stBottom"] {
  background: var(--parchment) !important;
  border-top: none !important;
  box-shadow: none !important;
}
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div,
[data-testid="stBottom"] section,
[data-testid="stBottomBlockContainer"],
.stBottomBlockContainer,
.stBottomBlockContainer > div,
section[data-testid="stBottom"],
section[data-testid="stBottom"] > div {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
}

/* ══ Keyframes ══════════════════════════════════════════════════════════════ */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position: 200% center; }
}
@keyframes breathe {
  0%, 100% { opacity: .5; transform: scale(1); }
  50%       { opacity: 1; transform: scale(1.15); }
}
@keyframes slideRight {
  from { opacity: 0; transform: translateX(-10px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* ══ HERO ════════════════════════════════════════════════════════════════════ */
.lc-hero {
  background: var(--navy);
  margin: 0 -1.5rem 0;
  padding: 0;
  position: relative;
  overflow: hidden;
  animation: fadeIn .6s var(--ease) both;
}

/* Layered atmospheric background */
.lc-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 120% 80% at 110% -10%, rgba(201,168,76,.12) 0%, transparent 50%),
    radial-gradient(ellipse 80% 120% at -10% 110%, rgba(29,52,112,.6) 0%, transparent 55%),
    radial-gradient(ellipse 60% 60% at 80% 80%, rgba(37,61,138,.4) 0%, transparent 50%);
  pointer-events: none;
}

/* Decorative circles */
.lc-hero::after {
  content: '';
  position: absolute;
  right: -80px;
  top: -80px;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  border: 1px solid rgba(201,168,76,.08);
  pointer-events: none;
}

.lc-hero-inner {
  position: relative;
  padding: 3.5rem 3rem 2.75rem;
}

/* Gold top rule */
.lc-hero-rule {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent 0%, var(--gold) 30%, var(--gold-2) 50%, var(--gold) 70%, transparent 100%);
  opacity: .7;
}

/* Circle decoration behind scales icon */
.lc-hero-circle {
  position: absolute;
  right: 2.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 180px;
  height: 180px;
  border-radius: 50%;
  border: 1px solid rgba(201,168,76,.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 72px;
  opacity: .15;
  pointer-events: none;
}

.lc-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .28em;
  text-transform: uppercase;
  color: var(--gold);
  opacity: .8;
  margin-bottom: 1.1rem;
}
.lc-eyebrow-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--gold);
  animation: breathe 2.8s ease-in-out infinite;
}
.lc-eyebrow-line {
  width: 28px; height: 1px;
  background: linear-gradient(90deg, var(--gold), transparent);
  opacity: .5;
}

.lc-title {
  font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
  font-size: clamp(36px, 5.5vw, 56px);
  font-weight: 900;
  color: #fff;
  line-height: 1.05;
  letter-spacing: -.025em;
  margin-bottom: .15em;
}
.lc-title-em {
  font-style: italic;
  font-weight: 700;
  color: rgba(255,255,255,.55);
  display: block;
  font-size: .9em;
  letter-spacing: -.01em;
}

.lc-sub {
  font-size: 13.5px;
  font-weight: 300;
  color: rgba(255,255,255,.42);
  line-height: 1.8;
  max-width: 430px;
  margin: 1rem 0 1.75rem;
  letter-spacing: .01em;
}

/* Code badges in hero */
.lc-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.lc-badge {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: rgba(255,255,255,.5);
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.1);
  padding: 5px 12px;
  border-radius: 3px;
  transition: all .2s var(--ease);
}

/* ══ SEARCH AREA ═════════════════════════════════════════════════════════════
   Streamlit's st.chat_input() is ALWAYS rendered in a sticky bottom container —
   it cannot be placed inside a custom HTML div. So we style the bottom container
   to look like a designed search dock, not an afterthought.
   ═════════════════════════════════════════════════════════════════════════════ */

/* The sticky bottom dock — make it look intentional */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
.stBottomBlockContainer {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
  border-top: 1px solid var(--parchment-3) !important;
  padding-top: .75rem !important;
  padding-bottom: .75rem !important;
  box-shadow: 0 -8px 32px rgba(12,27,58,.06) !important;
}
[data-testid="stBottom"] > *,
[data-testid="stBottom"] > * > *,
[data-testid="stBottomBlockContainer"] > *,
.stBottomBlockContainer > * {
  background: var(--parchment) !important;
  background-color: var(--parchment) !important;
}

/* The search input styling */
[data-testid="stChatInput"] {
  background: var(--white) !important;
  border: 1.5px solid var(--slate-4) !important;
  border-radius: 14px !important;
  box-shadow: var(--s2) !important;
  transition: border-color .22s var(--ease), box-shadow .22s var(--ease) !important;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--navy-3) !important;
  box-shadow: var(--s2), 0 0 0 4px rgba(29,52,112,.09) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
  font-size: 15px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 400 !important;
  line-height: 1.6 !important;
  padding: 14px 16px !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--slate-3) !important;
  font-style: italic !important;
  font-weight: 300 !important;
}

/* Send button */
[data-testid="stChatInputSubmitButton"] button {
  background: var(--navy) !important;
  border-radius: 10px !important;
  transition: background .18s var(--ease) !important;
}
[data-testid="stChatInputSubmitButton"] button:hover {
  background: var(--navy-3) !important;
}

/* ══ SAMPLE QUESTIONS ═══════════════════════════════════════════════════════ */
.lc-samples-wrap {
  padding: 2rem 0 .5rem;
  animation: fadeUp .5s var(--ease) .1s both;
}
.lc-samples-label {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--slate-3);
  margin-bottom: .5rem;
}
.lc-samples-hint {
  font-family: 'DM Sans', sans-serif; font-size: 12.5px; line-height: 1.5;
  color: var(--slate-3); margin: 0 0 1rem; max-width: 60ch;
}

/* Sample buttons */
.stButton > button {
  background: var(--white) !important;
  color: var(--ink-2) !important;
  border: 1px solid var(--slate-5) !important;
  border-left: 3px solid transparent !important;
  border-radius: 10px !important;
  padding: 12px 16px !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  font-family: 'DM Sans', sans-serif !important;
  text-align: left !important;
  line-height: 1.55 !important;
  width: 100% !important;
  box-shadow: var(--s1) !important;
  transition: all .2s var(--ease) !important;
  letter-spacing: .005em !important;
}
.stButton > button:hover {
  background: var(--parchment) !important;
  border-color: var(--gold-border) !important;
  border-left-color: var(--gold) !important;
  color: var(--navy) !important;
  transform: translateX(4px) !important;
  box-shadow: var(--s2) !important;
}

/* ══ ALERTS ═════════════════════════════════════════════════════════════════ */
.lc-alert {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: var(--gold-pale);
  border-left: 3px solid var(--gold);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  margin-bottom: 1.5rem;
  font-size: 13.5px;
  color: var(--amber);
  line-height: 1.6;
}

.lc-correction {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  background: var(--amber-bg);
  border-left: 3px solid var(--gold);
  border-radius: 0 8px 8px 0;
  padding: 10px 15px;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: var(--amber);
  line-height: 1.55;
  animation: fadeIn .3s ease both;
}

/* (clarifying UI removed) */

/* ══ VERDICT CARD ═══════════════════════════════════════════════════════════ */
.lc-verdict {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 22px;
  border-radius: 10px;
  margin-bottom: 18px;
  border: 1.5px solid;
  animation: fadeUp .3s var(--ease) both;
}
.lc-verdict-icon { font-size: 28px; flex-shrink: 0; line-height: 1; }
.lc-verdict-meta { flex: 1; }
.lc-verdict-title {
  font-size: 10px; font-weight: 700;
  letter-spacing: .18em; text-transform: uppercase;
  margin-bottom: 4px;
}
.lc-verdict-text { font-size: 14px; font-weight: 400; line-height: 1.55; }

.lc-verdict.compliant     { background: var(--green-bg); border-color: var(--green-b); color: var(--green); }
.lc-verdict.non-compliant { background: var(--red-bg);   border-color: var(--red-b);   color: var(--red); }
.lc-verdict.partial       { background: var(--amber-bg); border-color: var(--amber-b); color: var(--amber); }

/* ══ RESTATEMENT + ANALYSIS (the dissection) ════════════════════════════════ */
.lc-restate {
  font-size: 13.5px; line-height: 1.6; color: var(--slate-3); font-style: italic;
  margin-bottom: 16px; padding-left: 14px; border-left: 2px solid var(--line, #e2e8f0);
  animation: fadeUp .3s var(--ease) both;
}
.lc-issue {
  border: 1px solid var(--line, #e2e8f0); border-left-width: 3px; border-radius: 8px;
  padding: 13px 16px; margin-bottom: 10px; background: var(--card, #fff);
  animation: fadeUp .35s var(--ease) both;
}
.lc-issue-head {
  display: flex; align-items: center; gap: 9px;
  font-size: 14px; font-weight: 600; color: var(--ink, #0f172a); margin-bottom: 6px;
}
.lc-issue-chip {
  flex-shrink: 0; width: 20px; height: 20px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff;
}
.lc-issue-body { font-size: 13.5px; line-height: 1.65; color: var(--ink-2); }
.lc-issue-cite { margin-top: 8px; font-size: 11px; font-weight: 600; color: var(--navy-3); }
.lc-issue.ok        { border-left-color: var(--green); }
.lc-issue.risk      { border-left-color: var(--amber); }
.lc-issue.violation { border-left-color: var(--red); }
.lc-issue.info      { border-left-color: var(--navy-3); }
.lc-issue-chip.ok        { background: var(--green); }
.lc-issue-chip.risk      { background: var(--amber); }
.lc-issue-chip.violation { background: var(--red); }
.lc-issue-chip.info      { background: var(--navy-3); }

/* ══ ANSWER CARDS ═══════════════════════════════════════════════════════════ */
.lc-block { margin-bottom: 16px; animation: fadeUp .35s var(--ease) both; }
.lc-section-label {
  font-size: 9.5px; font-weight: 700; letter-spacing: .2em;
  text-transform: uppercase; color: var(--slate-3); margin-bottom: 9px;
}
.lc-lead {
  font-size: 15px; line-height: 1.75; color: var(--ink-2); font-weight: 400;
  margin-bottom: 18px; padding: 2px 0 2px 16px;
  border-left: 3px solid var(--navy-3);
  animation: fadeUp .35s var(--ease) both;
}
ul.lc-req, ul.lc-action-list { list-style: none; padding-left: 0 !important; margin: 0 !important; }
ul.lc-req li {
  position: relative; padding-left: 26px; margin-bottom: 9px;
  font-size: 14px; line-height: 1.6; color: var(--ink-2); font-weight: 400;
}
ul.lc-req li::before {
  content: "✓"; position: absolute; left: 0; top: -1px;
  color: var(--green); font-weight: 700; font-size: 14px;
}
.lc-action {
  background: var(--gold-pale); border: 1px solid var(--gold-border);
  border-radius: 10px; padding: 15px 20px; margin-bottom: 18px;
  animation: fadeUp .35s var(--ease) both;
}
.lc-action .lc-section-label { color: var(--amber); }
ul.lc-action-list li {
  position: relative; padding-left: 24px; margin-bottom: 8px;
  font-size: 14px; line-height: 1.6; color: var(--ink-2); font-weight: 500;
}
ul.lc-action-list li::before {
  content: "→"; position: absolute; left: 0; top: 0;
  color: var(--gold); font-weight: 700;
}
ul.lc-action-list li:last-child, ul.lc-req li:last-child { margin-bottom: 0; }

/* Applies-to-your-case — verified establishment-size / tenure thresholds */
.lc-applies {
  background: var(--navy-pale, #eef2f7); border: 1px solid var(--navy-3, #c7d3e6);
  border-radius: 10px; padding: 15px 20px; margin-bottom: 18px;
  animation: fadeUp .35s var(--ease) both;
}
.lc-applies .lc-section-label { color: var(--navy, #21314f); }
ul.lc-applies-list { list-style: none; padding-left: 0 !important; margin: 0 !important; }
ul.lc-applies-list li {
  position: relative; padding-left: 22px; margin-bottom: 9px;
  font-size: 13.5px; line-height: 1.6; color: var(--ink-2); font-weight: 400;
}
ul.lc-applies-list li::before {
  content: "§"; position: absolute; left: 0; top: 0;
  color: var(--navy, #21314f); font-weight: 700;
}
ul.lc-applies-list li:last-child { margin-bottom: 0; }

/* Intake clarifying card + cross-reference chips */
.lc-intake-head { font-size: 14.5px; font-weight: 600; color: var(--ink-2); margin-bottom: 6px; }
.lc-intake-q {
  font-family: 'Playfair Display', serif; font-style: italic;
  color: var(--slate-3); font-size: 13.5px; margin-bottom: 12px;
}
.lc-xref-label {
  font-size: 9.5px; font-weight: 700; letter-spacing: .2em; text-transform: uppercase;
  color: var(--slate-3); margin: 16px 0 8px;
}

/* Citation pills */
.lc-cite-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0 2px;
}
.lc-cite {
  font-size: 11px; font-weight: 600; letter-spacing: .02em;
  color: var(--navy); background: var(--gold-pale);
  border: 1px solid var(--gold-border); padding: 4px 11px; border-radius: 999px;
}

/* Collapsible statutory text */
[data-testid="stExpander"] {
  border: 1px solid var(--slate-5) !important; border-radius: 8px !important;
  background: var(--white) !important; margin: 8px 0 4px !important;
  box-shadow: none !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary,
[data-testid="stExpander"] [data-testid="stExpanderToggle"] {
  font-size: 12px !important; font-weight: 600 !important;
  color: var(--navy-2) !important; letter-spacing: .03em !important;
}
.lc-auth-cite {
  font-family: 'Playfair Display', serif; font-size: 13.5px; font-weight: 700;
  color: var(--navy); margin: 12px 0 5px;
}
.lc-auth-cite:first-child { margin-top: 2px; }
.lc-auth-title { font-family: 'DM Sans', sans-serif; font-weight: 600; font-style: italic;
  color: var(--ink-soft, #5b6472); }
blockquote.lc-auth-quote {
  border-left: 3px solid var(--gold); background: var(--gold-pale);
  border-radius: 0 8px 8px 0; margin: 0 0 6px; padding: 10px 14px;
  font-size: 13px; line-height: 1.7; color: var(--ink-2);
}

/* Disclaimer */
.lc-disclaimer {
  font-size: 11.5px; font-style: italic; color: var(--slate-2);
  margin-top: 18px; padding-top: 12px; border-top: 1px solid var(--parchment-3);
}

/* ══ OLD ↔ NEW COMPARISON ═══════════════════════════════════════════════════ */
.lc-cmp-headline {
  font-family: 'Playfair Display', serif; font-size: 16px; font-weight: 700;
  color: var(--navy); background: var(--gold-pale); border: 1px solid var(--gold-border);
  border-radius: 10px; padding: 13px 18px; margin-bottom: 18px; line-height: 1.5;
}
.lc-cmp-topic {
  font-size: 10px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: var(--slate-3); margin: 6px 0 8px;
}
.lc-cmp-card {
  border-radius: 10px; padding: 13px 15px; height: 100%;
  border: 1px solid var(--slate-5); background: var(--white);
}
.lc-cmp-card.old { background: var(--parchment-2); border-color: var(--parchment-3); }
.lc-cmp-card.new { background: #F4F7FF; border-color: #C9D6F5; }
.lc-cmp-tag {
  font-size: 9.5px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  margin-bottom: 6px;
}
.lc-cmp-tag.old { color: var(--slate-2); }
.lc-cmp-tag.new { color: var(--navy); }
.lc-cmp-body { font-size: 13.5px; line-height: 1.6; color: var(--ink-2); }
.lc-cmp-card.old .lc-cmp-body { color: var(--slate); }
.lc-cmp-cite {
  font-size: 10.5px; font-weight: 600; color: var(--slate-2);
  margin-top: 8px; padding-top: 7px; border-top: 1px dashed var(--slate-5);
}
.lc-cmp-card.new .lc-cmp-cite { color: var(--navy); }
.lc-cmp-impact {
  font-size: 13px; line-height: 1.55; color: var(--ink-2);
  background: var(--gold-pale); border-left: 3px solid var(--gold);
  border-radius: 0 8px 8px 0; padding: 9px 14px; margin: 10px 0 22px;
}
.lc-cmp-impact span { color: var(--amber); font-weight: 700; }

/* ══ VERBATIM-QUOTE GUARDRAIL ════════════════════════════════════════════════ */
.lc-trust {
  font-size: 11.5px; font-weight: 600; letter-spacing: .01em;
  border-radius: 8px; padding: 7px 12px; margin: 8px 0 4px;
}
.lc-trust.ok   { color: var(--green); background: var(--green-bg); border: 1px solid var(--green-b); }
.lc-trust.warn { color: var(--red);   background: var(--red-bg);   border: 1px solid var(--red-b); }
.lc-verified {
  font-size: 9.5px; font-weight: 700; letter-spacing: .04em; color: var(--green);
  background: var(--green-bg); border: 1px solid var(--green-b);
  padding: 1px 7px; border-radius: 999px; margin-left: 6px; white-space: nowrap;
}
.lc-unverified {
  font-size: 9.5px; font-weight: 700; letter-spacing: .04em; color: var(--red);
  background: var(--red-bg); border: 1px solid var(--red-b);
  padding: 1px 7px; border-radius: 999px; margin-left: 6px; white-space: nowrap;
}
blockquote.lc-auth-quote.unverified {
  border-left-color: var(--red) !important; background: var(--red-bg) !important;
}

/* ══ CHAT MESSAGES ══════════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: .25rem 0 !important;
  animation: fadeUp .4s var(--ease) both;
}

/* Hide ALL avatar elements — covers every Streamlit version's data-testid variants */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"],
[class*="avatarImage"],
[class*="avatar"] img,
.stChatMessage [data-testid*="Avatar"] { display: none !important; }

/* User bubble — target by role attribute which is more stable than avatar presence */
[data-testid="stChatMessage"][data-role="user"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--navy) !important;
  border-radius: 20px 20px 5px 20px !important;
  padding: 14px 22px !important;
  margin-left: 80px !important;
  margin-right: 0 !important;
  box-shadow: var(--s3) !important;
}
[data-testid="stChatMessage"][data-role="user"] [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"][data-role="user"] [data-testid="stChatMessageContent"] p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] p {
  color: rgba(255,255,255,.85) !important;
  font-size: 14px !important;
  font-weight: 300 !important;
  line-height: 1.7 !important;
}

/* Assistant card */
[data-testid="stChatMessage"][data-role="assistant"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background: var(--white) !important;
  border: 1px solid var(--slate-5) !important;
  border-top: 3px solid var(--navy) !important;
  border-radius: 4px 20px 20px 20px !important;
  padding: 22px 26px 20px !important;
  margin-right: 40px !important;
  margin-left: 0 !important;
  box-shadow: var(--s2) !important;
  transition: box-shadow .25s var(--ease) !important;
}
[data-testid="stChatMessage"][data-role="assistant"]:hover,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]):hover {
  box-shadow: var(--s3) !important;
}

/* Typography inside chat */
[data-testid="stChatMessageContent"] {
  font-size: 14.5px !important;
  line-height: 1.8 !important;
  color: var(--ink-2) !important;
  font-weight: 300 !important;
  font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stChatMessageContent"] p { margin: 0 0 .65rem !important; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0 !important; }
[data-testid="stChatMessageContent"] strong {
  color: var(--navy) !important;
  font-weight: 600 !important;
}
[data-testid="stChatMessageContent"] em { color: var(--slate) !important; }

/* Blockquote = statute text */
[data-testid="stChatMessageContent"] blockquote {
  border-left: 3px solid var(--gold) !important;
  margin: 1rem 0 !important;
  padding: 10px 0 10px 18px !important;
  color: var(--ink-2) !important;
  font-style: normal !important;
  font-size: 13.5px !important;
  background: var(--gold-pale) !important;
  border-radius: 0 8px 8px 0 !important;
  line-height: 1.75 !important;
}

/* Section headings */
[data-testid="stChatMessageContent"] h3 {
  font-family: 'Playfair Display', serif !important;
  font-size: 16px !important;
  font-weight: 700 !important;
  color: var(--navy) !important;
  margin: 1.5rem 0 .6rem !important;
  padding-bottom: 7px !important;
  border-bottom: 1px solid var(--parchment-3) !important;
}
[data-testid="stChatMessageContent"] h4 {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--slate) !important;
  text-transform: uppercase !important;
  letter-spacing: .08em !important;
  margin: 1.2rem 0 .5rem !important;
}

/* Lists */
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
  padding-left: 1.5rem !important;
  margin: .45rem 0 .8rem !important;
}
[data-testid="stChatMessageContent"] li {
  margin-bottom: .4rem !important;
  line-height: 1.65 !important;
}

/* Code */
[data-testid="stChatMessageContent"] code {
  background: var(--parchment-2) !important;
  color: var(--navy-2) !important;
  padding: 2px 7px !important;
  border-radius: 4px !important;
  font-size: 12px !important;
  font-family: 'SF Mono', 'Fira Code', monospace !important;
  border: 1px solid var(--parchment-3) !important;
}

/* ══ SOURCE CHIPS ROW ═══════════════════════════════════════════════════════ */
.lc-src-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--slate-5);
}
.lc-src-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--slate-3);
  margin-right: 3px;
}
.lc-src-chip {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--white);
  background: var(--navy);
  padding: 4px 11px;
  border-radius: 4px;
}
.lc-none-chip {
  font-size: 10px;
  color: var(--slate-3);
  background: var(--parchment-2);
  border: 1px solid var(--slate-5);
  padding: 4px 11px;
  border-radius: 4px;
  font-style: italic;
}

/* ══ SPINNER ════════════════════════════════════════════════════════════════ */
[data-testid="stSpinner"] > div > div {
  border-color: var(--parchment-3) !important;
  border-top-color: var(--navy) !important;
}

/* ══ FOOTER ═════════════════════════════════════════════════════════════════ */
.lc-footer {
  font-size: 11px;
  color: var(--slate-3);
  text-align: center;
  margin-top: 3rem;
  line-height: 2.2;
  letter-spacing: .04em;
  padding-top: 1.5rem;
  border-top: 1px solid var(--parchment-3);
}
.lc-footer strong { color: var(--slate-2); font-weight: 500; }

/* ══ SCROLLBAR ══════════════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--slate-4); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--slate-3); }

::selection { background: var(--navy); color: #fff; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Corpus loader
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_corpus():
    return corpus.load_corpus()

CFG, CORPUS_DATA = get_corpus()
LOADED = dict(CORPUS_DATA)


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock client
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_bedrock_client():
    try:
        api_key = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        region  = st.secrets.get("AWS_REGION", "us-east-1")
        if api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
        return boto3.client("bedrock-runtime", region_name=region)
    except Exception:
        return None

def _has_key() -> bool:
    try:
        k = st.secrets.get("AWS_BEARER_TOKEN_BEDROCK", "")
        return bool(k and k.strip())
    except Exception:
        return False

def _model_id() -> str:
    """Effective model ID — overridable via the BEDROCK_MODEL_ID secret."""
    try:
        return (st.secrets.get("BEDROCK_MODEL_ID", "") or "").strip() or MODEL_ID
    except Exception:
        return MODEL_ID

def _model_label() -> str:
    """Friendly model name for the footer, derived from the effective model id."""
    mid = _model_id().lower()
    if "nova-pro" in mid:   return "Amazon Nova Pro"
    if "nova" in mid:       return "Amazon Nova"
    if "claude" in mid:     return "Anthropic Claude"
    if "llama" in mid:      return "Meta Llama"
    if "mistral" in mid:    return "Mistral"
    return _model_id()


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM = """You are an expert Indian Labour Law compliance assistant for HR managers. You think like
a labour lawyer: you DISSECT the manager's situation into the distinct legal issues it raises, ground
each issue in the governing Section/Rule, reason from the law to THEIR facts, and only then conclude.

You receive statutory text from India's four Labour Codes and their Central Rules, plus the HR
manager's question or situation.

Respond with a SINGLE JSON object and NOTHING else — no prose, no markdown, no ``` fences.

Choose "type":
- "compliance" — the manager describes something they did or plan to do (a verdict is needed).
- "info" — they ask what something means or what their obligations are.

JSON shape:
{
  "type": "compliance" | "info",
  "restatement": "one sentence restating the situation/question in your own words (shows you understood it)",
  "verdict": {"status": "compliant" | "non-compliant" | "partial", "summary": "one-sentence bottom line"},
  "analysis": [
    {
      "issue": "the specific legal question this situation raises (short)",
      "finding": "2-4 sentences: what the governing provision requires AND how it applies to THESE facts",
      "status": "ok" | "risk" | "violation" | "info",
      "citation": "Section X / Rule Y — [Code Name]"
    }
  ],
  "actions": ["imperative step the manager must take now", ...],
  "authorities": [{"citation": "Section X / Rule X — [Code Name]", "quote": "exact statutory text"}]
}

Field rules:
- ALWAYS fill "restatement" and "analysis". "analysis" is the heart of the answer: 1-4 issues, each
  spotting one legal question, naming the governing provision, and APPLYING it to the manager's
  facts (not a generic summary). Order issues from most to least important.
- type "compliance": fill "verdict"; each issue "status" is "ok" (the stated facts satisfy the
  provision) / "risk" (the provision applies but the stated facts do NOT show whether it was met —
  open/conditional) / "violation" (the stated facts AFFIRMATIVELY show it was NOT met); fill
  "actions" with concrete next steps (only when NOT fully compliant, else []).
- verdict.status MUST match the WORST issue, never overstate: if any issue is "violation" →
  "non-compliant"; else if any issue is "risk" → "partial"; only when EVERY issue is "ok" →
  "compliant". A "compliant" verdict with a risk/violation issue or any outstanding action is wrong.
- type "info": set "verdict" to null; each issue "status" is "info"; "actions" may list helpful next
  steps or be [].
- Do NOT assume facts the manager did not state — in EITHER direction. The manager not MENTIONING a
  required step (notice, compensation, inquiry, permission) is NOT evidence it was skipped (that would
  be "violation") nor that it was done (that would be "ok") — it is "risk". Mark such an unstated step
  "risk" (which makes verdict.status "partial") and state it CONDITIONALLY ("compliant only if you
  gave the §X notice + compensation; if you did not, that step is still outstanding"). Reserve
  "violation" for a step the stated facts affirmatively show was missed ("I gave two days' notice").
- WORKED EXAMPLE of the rules above — "I retrenched a worker (3 yrs' service, 120-employee firm) —
  was that correct?" says nothing about notice or compensation. Eligibility to retrench → "ok"; the
  one-month notice and the 15-days-per-year compensation are UNSTATED → each "risk" (not "ok", not
  "violation"). Worst issue is "risk", so verdict.status = "partial", summary = "Lawful only if you
  served one month's notice (or wages in lieu) and paid 15 days' wages per completed year — on the
  facts given those steps are unconfirmed", and "actions" list those verifications.
- ELIGIBILITY-GATED ENTITLEMENTS (gratuity, maternity benefit, lay-off / retrenchment compensation,
  annual bonus, leave) turn on a THRESHOLD the worker must first CROSS — e.g. gratuity needs not less
  than 5 years' continuous service; maternity benefit needs at least 80 days worked in the 12 months
  before the expected delivery; leave with wages needs 180 days in the calendar year. Decide them in
  this strict order: (1) does the worker CROSS the threshold, OR does a STATUTORY WAIVER of the
  threshold apply? (gratuity's 5-year minimum is expressly WAIVED where employment ends on the
  employee's DEATH or DISABLEMENT — then it is payable regardless of length of service). (2) if the
  threshold is not crossed and no waiver applies — the employer owes the benefit to nobody, so
  WITHHOLDING OR REFUSING it is COMPLIANT, status "ok"; it is NOT a violation and needs no corrective
  action; (3) if the worker DOES cross it (or a waiver applies) — compare what the employer ACTUALLY
  did against what is owed: refused, withheld or short-paid → "violation" → verdict NON-COMPLIANT;
  paid in full → "ok". Being entitled does NOT by itself make a refusal "compliant" — entitlement
  plus refusal is a violation. A figure stated as "not less than", "at least" or "or more" INCLUDES
  its boundary — exactly 5 years qualifies for gratuity, exactly 80 days qualifies for maternity.
- WORKED EXAMPLE (below threshold = compliant) — "An employee resigned after 4 years' continuous
  service and we paid no gratuity." Gratuity needs not less than 5 years; 4 years does NOT cross the
  threshold and no waiver applies, so the employee is not entitled and withholding it is lawful →
  status "ok", verdict.status = "compliant", actions [].
- WORKED EXAMPLE (waiver overrides threshold) — "An employee DIED after 3 years and we refused
  gratuity for want of 5 years' service." Death WAIVES the 5-year minimum, so gratuity IS payable to
  the nominee/family; refusing it → "violation" → verdict NON-COMPLIANT.
- WORKED EXAMPLE (above threshold, refused = violation) — "We refused maternity benefit to a woman
  who had worked exactly 80 days in the 12 months before her expected delivery." 80 days MEETS the
  not-less-than-80-days bar, so she IS entitled; refusing an entitled worker → "violation" → verdict
  NON-COMPLIANT (NOT "compliant" merely because she qualified).
- A threshold cuts BOTH WAYS: just as failing it removes the worker's ENTITLEMENT, it also removes the
  employer's matching OBLIGATION. Section 70's one-month notice + 15-days-per-year retrenchment
  compensation are owed only to a worker with NOT LESS THAN ONE YEAR of continuous service; for a
  worker BELOW one year those duties are not triggered, so retrenching with no notice or compensation
  is COMPLIANT, status "ok" — do NOT recast the unmet threshold as a notice/compensation "violation".
- WORKED EXAMPLE (obligation not triggered below threshold) — "We retrenched a worker with only 8
  months' service, no notice or compensation." Under one year, so the §70 notice/compensation duties
  do not arise → status "ok", verdict.status = "compliant".
- Every "analysis[].citation" MUST also appear in "authorities" with its VERBATIM quote. When a
  Central Rule prescribes the procedure, forms, timelines, registers or rates for a Section you rely
  on, cite and quote the Rule as well as the Section.
- Each supplied excerpt is headed with its provision title (e.g. "Section 9 — Power to fix floor
  wage"). Refer to provisions by that title in your finding so it reads naturally, but keep
  "citation" in the exact "Section X / Rule Y — [Code Name]" form.

ABSOLUTE RULES:
- NEVER invent or paraphrase statutory text. "authorities[].quote" must be verbatim from the
  supplied excerpts only.
- NEVER use outside legal knowledge not in the supplied text.
- CITE ONLY the four 2020 Codes and their Central Rules (Code on Wages, 2019; Industrial Relations
  Code, 2020; Code on Social Security, 2020; Occupational Safety, Health and Working Conditions Code,
  2020). NEVER cite a pre-2020 repealed Act — e.g. the Payment of Gratuity Act, 1972; Maternity
  Benefit Act, 1961; Minimum Wages Act, 1948; Payment of Bonus Act, 1965; Industrial Disputes Act,
  1947 — even if you recall it; the corresponding duty now lives in a 2020 Code, and that is what you
  must cite (gratuity → Code on Social Security §53, etc.).
- If no supplied excerpt is relevant, return "analysis": [], "authorities": [] and say so plainly in
  "restatement"/"verdict.summary".
- If the supplied text answers only PART of the question, answer that part fully and state plainly
  what the supplied provisions do NOT cover — never close the gap with outside knowledge or a guess.
- Be specific in plain English (numbers, days, thresholds), taking each figure VERBATIM from the
  exact provision you cite — never carry a number across Sections (a one-month notice in the general
  retrenchment Section is not the three-month notice in the special-establishment Section).
- When the law sets a MINIMUM ("at least", "not less than", "minimum of"), anything AT or ABOVE it
  COMPLIES; when it sets a MAXIMUM ("not more than", "up to", "shall not exceed"), anything AT or
  BELOW it complies. State the comparison explicitly before you conclude — e.g. "the minimum bonus is
  8.33%; the employer paid 10%, and 10% ≥ 8.33%, so this meets the minimum → 'ok'". Do NOT flag a
  figure that satisfies the rule as a violation.
- Output VALID JSON. Escape quotes and newlines inside strings. No text outside the JSON object."""


COMPARISON_SYSTEM = """You are an expert Indian Labour Law assistant for HR managers.

You receive: statutory text from the CURRENT Code(s) in force, statutory text from the PREVIOUS
(now-repealed) Act(s), and the HR manager's question about WHAT CHANGED.

Respond with a SINGLE JSON object and NOTHING else — no prose, no markdown, no ``` fences:
{
  "type": "comparison",
  "headline": "one plain-English sentence naming the single most important change",
  "changes": [
    {
      "topic": "short label (e.g. 'Retrenchment notice')",
      "old": "what the PREVIOUS Act required — plain English, exact numbers/thresholds",
      "old_cite": "Section X — [previous Act name, year]",
      "new": "what the CURRENT Code requires — plain English, exact numbers/thresholds",
      "new_cite": "Section X / Rule X — [Code name]",
      "impact": "what the HR manager must actually do differently now"
    }
  ],
  "authorities": [{"citation": "Section X — [Act/Code]", "quote": "exact verbatim statutory text"}]
}

RULES:
- Give the 2-4 changes that matter most to HR. Be concrete: days, amounts, thresholds, percentages.
- "old"/"old_cite" come ONLY from the PREVIOUS-law text; "new"/"new_cite" ONLY from the
  CURRENT-law text. Never swap them.
- If the previous law had no equivalent provision, set "old" to "No equivalent provision" and
  "old_cite" to "".
- Report only changes the supplied texts actually show; never manufacture a difference. If the two
  texts say the same thing on a point, omit it rather than inventing a change.
- authorities[].quote is VERBATIM from the supplied text only — never invent or paraphrase statute.
- Rely only on the supplied excerpts; use outside knowledge for nothing.
- Output VALID JSON. Escape quotes and newlines. No text outside the JSON object."""


# ─────────────────────────────────────────────────────────────────────────────
# Direct answering (clarification step removed)
# ─────────────────────────────────────────────────────────────────────────────
# (Clarification step removed — every query is answered directly, no "which code?" chips.)


# ─────────────────────────────────────────────────────────────────────────────
# Streaming
# ─────────────────────────────────────────────────────────────────────────────
def _friendly_bedrock_error(e: Exception) -> str:
    """Turn raw AWS errors into clear, actionable guidance for the operator."""
    msg = str(e)
    low = msg.lower()
    if ("payment" in low or "marketplace subscription" in low
            or "invalid_payment_instrument" in low):
        return (
            "\n\n⚠️ **AWS billing isn't active for this account yet.**\n"
            "Add a valid card in **AWS Console → Billing → Payment preferences** (some cards "
            "need a small verification charge to clear), wait ~2 minutes, and try again. "
            "Amazon Nova is a first-party model and needs no Marketplace subscription, so once "
            "billing is valid it should work."
        )
    if ("model identifier is invalid" in low or "resourcenotfound" in low
            or "is not supported" in low or "isn't supported" in low
            or "don't have access to the model" in low
            or "do not have access to the model" in low):
        return (
            "\n\n⚠️ **The model isn't available in this AWS region.** Amazon Nova Pro is not "
            "offered everywhere (e.g. not in Mumbai `ap-south-1`). Set the **`AWS_REGION`** "
            "secret to a supported region such as `us-east-1` or `ap-southeast-3` (Jakarta) — "
            "or set **`BEDROCK_MODEL_ID`** to a model your region supports."
        )
    if ("accessdenied" in low or "not authorized" in low
            or "could not be validated" in low):
        return (
            "\n\n⚠️ **AWS denied access.** Confirm `AWS_BEARER_TOKEN_BEDROCK` is valid and that "
            "its identity has the `bedrock:InvokeModel` permission, and that `AWS_REGION` is a "
            "region where the model is available."
        )
    return f"\n\n⚠️ Error contacting the model: {msg}"


def _parse_answer(text: str) -> dict:
    """Parse the model's JSON answer; fall back to raw text on any failure."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    i, j = raw.find("{"), raw.rfind("}")
    if i != -1 and j > i:
        try:
            data = json.loads(raw[i : j + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"_raw": text or ""}


def _converse_json(system: str, user_text: str,
                   max_tokens: int = 8192, temperature: float = 0.25) -> dict:
    """Single non-streaming Converse call returning parsed JSON (or a raw-text fallback).
    Headroom (8192 tokens) lets the model reason through several issues without truncation;
    a slightly warmer temperature (0.25) reads less robotic while staying accurate for law."""
    client = get_bedrock_client()
    if not client:
        return {"_raw": "⚠️ Bedrock client error. Check secrets."}
    if not _has_key():
        return {"_raw": "⚠️ Add **AWS_BEARER_TOKEN_BEDROCK** and **AWS_REGION** in "
                        "*App → Settings → Secrets*."}
    try:
        resp = client.converse(
            modelId=_model_id(),
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        return _parse_answer(resp["output"]["message"]["content"][0]["text"])
    except Exception as e:
        return {"_raw": _friendly_bedrock_error(e)}


# A "compliant" headline must never sit above an unmet or unconfirmed issue. The model classifies
# each issue (ok/risk/violation) reliably but is erratic about rolling them into verdict.status, so
# we enforce a deterministic floor: the verdict is at least as severe as its worst issue.
_ISSUE_TO_VERDICT = {"violation": "non-compliant", "risk": "partial", "ok": "compliant"}
_VERDICT_RANK = {"compliant": 0, "partial": 1, "non-compliant": 2}


def _reconcile_verdict(data: dict) -> dict:
    """Raise verdict.status to match the worst issue when the model under-rates it (e.g. keeps a
    'compliant' headline despite a 'risk' issue). Never lowers severity; leaves info-type answers
    and verdicts with no classified issues untouched."""
    if not isinstance(data, dict) or data.get("type") != "compliance":
        return data
    verdict = data.get("verdict")
    if not isinstance(verdict, dict):
        return data
    derived = [_ISSUE_TO_VERDICT[s] for s in
               (str(a.get("status", "")).strip().lower()
                for a in (data.get("analysis") or []) if isinstance(a, dict))
               if s in _ISSUE_TO_VERDICT]
    if not derived:
        return data
    worst = max(derived, key=lambda v: _VERDICT_RANK[v])
    orig = str(verdict.get("status", "")).strip().lower()
    if _VERDICT_RANK.get(orig, -1) >= _VERDICT_RANK[worst]:
        return data  # already at least as severe — keep the model's status and summary
    verdict["status"] = worst
    summ = str(verdict.get("summary", ""))
    if not any(w in summ.lower() for w in ("if ", "only if", "provided", "unless", "outstanding",
                                           "subject to")):
        verdict["summary"] = ("Compliant only if each flagged step below was actually carried out; "
                              "on the facts stated that cannot be confirmed."
                              if worst == "partial" else
                              "Non-compliant on the flagged step(s) below.")
    return data


def generate_answer(messages: list[dict]) -> dict:
    """Structured single answer (verdict / info)."""
    return _reconcile_verdict(_converse_json(SYSTEM, messages[-1]["content"]))


def generate_comparison(user_text: str) -> dict:
    """Old-Act vs new-Code 'what changed' comparison."""
    return _converse_json(COMPARISON_SYSTEM, user_text)


QUERY_REWRITE_SYSTEM = """You turn an HR manager's question or situation into a compact set of SEARCH
KEYWORDS for looking up Indian labour-law provisions. Expand plain-English wording into the statute's
own terms and close synonyms — e.g. "fire / let go / sack" -> "termination dismissal retrenchment
discharge", "time off for a baby" -> "maternity benefit leave", "PF" -> "provident fund".
Output ONLY keywords and short phrases, space-separated, lowercase, no punctuation, no explanation."""

_query_terms_cache: dict = {}

def analyze_query(raw_q: str) -> str:
    """Expand a plain-English question into legal search keywords, ADDED to the retrieval query so
    paraphrased questions still hit the right Sections. Fail-safe: returns "" on any error or when
    no key is configured, so retrieval falls back to exactly today's behaviour."""
    q = (raw_q or "").strip()
    if not q or not _has_key():
        return ""
    if q in _query_terms_cache:
        return _query_terms_cache[q]
    client = get_bedrock_client()
    if not client:
        return ""
    try:
        resp = client.converse(
            modelId=_model_id(),
            system=[{"text": QUERY_REWRITE_SYSTEM}],
            messages=[{"role": "user", "content": [{"text": q}]}],
            inferenceConfig={"maxTokens": 120, "temperature": 0.0},
        )
        out = resp["output"]["message"]["content"][0]["text"]
        out = re.sub(r"[^a-z0-9\s/-]", " ", out.lower())   # keep a clean keyword line only
        out = re.sub(r"\s+", " ", out).strip()[:200]
        if out:
            _query_terms_cache[q] = out
        return out
    except Exception:
        return ""


_COMPARE_RE = re.compile(
    r"\b(what changed|has changed|changed (?:from|since|in)|old act|old law|earlier law|"
    r"previously|before the code|used to|compared to|comparison|difference|differ|"
    r"new vs old|old vs new|replaced|repeal)\b", re.I)

def _is_comparison(query: str) -> bool:
    return bool(_COMPARE_RE.search(query))


def _verify_quotes(data: dict) -> dict:
    """Guardrail: anchor each citation to the REAL provision in the corpus (show that text —
    guaranteed verbatim); otherwise verify the model's quote against the full statute, so a
    genuine quote is never falsely flagged and a fabricated one never passes."""
    if not isinstance(data, dict):
        return data
    auths = data.get("authorities")
    if not isinstance(auths, list):
        return data
    hay = corpus.full_corpus_norm(LOADED)
    for a in auths:
        if not isinstance(a, dict):
            continue
        cit = str(a.get("citation", ""))
        a["title"] = corpus.lookup_title(LOADED, cit)   # marginal title, e.g. "Floor wage"
        src = corpus.lookup_citation(LOADED, cit)
        if src:
            a["verified"] = True
            a["source_text"] = src            # display the real provision text
        elif str(a.get("quote", "")).strip():
            a["verified"] = corpus.quote_supported(a["quote"], hay)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_PROSPECTIVE_RE = re.compile(
    r"\b(want to|wish to|plan(?:ning)? to|going to|intend to|thinking of|considering|about to|"
    r"can i|may i|should i|how (?:do|should) i|do i need to|what'?s the [\w\s]*process)\b", re.I)
_PAST_ACT_RE = re.compile(
    r"\b(retrenched|terminated|dismissed|fired|sacked|closed down|laid (?:him|her|them|off)|"
    r"did i|already|last (?:week|month|year)|have (?:i )?(?:retrenched|terminated|dismissed|fired))\b",
    re.I)

def _is_prospective(q: str) -> bool:
    """Future intent ('want to', 'can I', 'planning to') with no completed-act marker — so a
    not-yet-taken action is framed as guidance, not stamped 'non-compliant'."""
    return bool(_PROSPECTIVE_RE.search(q or "") and not _PAST_ACT_RE.search(q or ""))

# Chapter X (special provisions) of the IR Code binds only from 300 workers. Below that its
# prior-permission Sections must not even reach the model: a binding note + explicit naming still
# didn't stop the model citing §79 at 120 workers, so we drop them from the compliance grounding.
_CHAPTER_X_EXCL = {"retrench": {77, 79}, "closure": {77, 80}}

def _excluded_ir_sections(topic: str, got: dict) -> set:
    size = (got or {}).get("size", "")
    sub300 = ("fewer than 50" in size) or ("50 to 299" in size)
    return _CHAPTER_X_EXCL.get(topic, set()) if sub300 else set()

def build_prompt(query: str, all_results: dict, applicability=None) -> str:
    grounding = corpus.render_all_results(all_results)
    no_prov   = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
    parts     = [f"=== STATUTORY TEXT ===\n{grounding}"]
    if no_prov:
        parts.append(
            "=== NO PROVISION FOUND ===\n"
            + "\n".join(f"• {n}" for n in no_prov)
        )
    if applicability:
        # The establishment-size / length-of-service gating decides WHICH provisions apply
        # (e.g. prior-permission Chapter X duties only from 300 workers). Give it to the model
        # as binding so the verdict can't over-apply a provision the facts rule out — the
        # notes name the excluded Sections explicitly because a descriptive note alone wasn't
        # enough to stop the model citing §79 below 300 workers.
        parts.append(
            "=== APPLICABLE THRESHOLDS (binding — your verdict MUST obey these) ===\n"
            "Determined from the manager's facts; they decide which provisions apply. Apply ONLY "
            "provisions consistent with them. If a threshold says a Section or prior Government "
            "permission does NOT apply at this size, you MUST NOT cite it, call its absence a "
            "violation, or list it as a required action.\n"
            + "\n".join(f"• {n}" for n in applicability))
    if _is_prospective(query):
        parts.append(
            "=== FRAMING ===\n"
            "This describes a PLANNED/PROPOSED action, not a completed one. Set \"verdict.status\" "
            "to \"partial\" and put the steps needed to comply in \"actions\"; do not label a "
            "not-yet-taken action \"non-compliant\".")
    parts.append(f"=== QUESTION ===\n{query}")
    return "\n\n".join(parts)

def build_comparison_prompt(query: str, all_results: dict) -> str:
    new_g = corpus.render_all_results(all_results)
    olds = []
    for cid, r in all_results.items():
        if not r["found"]:
            continue
        oc = corpus.search_old(LOADED[cid], query, k=6)
        if oc:
            olds.append(corpus.render_chunks(oc))
    old_g = "\n\n".join(olds) if olds else "(No repealed-Act text found for this topic.)"
    return (f"=== CURRENT LAW (in force) ===\n{new_g}\n\n"
            f"=== PREVIOUS LAW (repealed Acts) ===\n{old_g}\n\n"
            f"=== QUESTION ===\n{query}")

def _correction_html(corrections):
    pairs = ", ".join(
        f'<strong>{o}</strong> → <strong>{f}</strong>' for o, f in corrections
    )
    return f'<div class="lc-correction">✏️ Interpreted as: {pairs}</div>'

def _src_row_html(sources, no_provision):
    src  = "".join(f'<span class="lc-src-chip">{s}</span>' for s in sources)
    none = "".join(f'<span class="lc-none-chip">∅ {n}</span>' for n in no_provision)
    return (
        f'<div class="lc-src-row">'
        f'<span class="lc-src-label">Sources</span>{src}{none}'
        f'</div>'
    )

DISCLAIMER = ("⚖️ Informational only — not legal advice. "
              "Consult a qualified advisor for specific situations.")
_VERDICT = {
    "compliant":     ("✔", "Compliant"),
    "non-compliant": ("✖", "Non-Compliant"),
    "partial":       ("⚠", "Partially Compliant"),
}

def _esc(x) -> str:
    return html.escape(str(x if x is not None else ""))

def _esc_ml(x) -> str:
    return _esc(x).replace("\n", "<br>")

def _bullets(items) -> str:
    return "".join(f"<li>{_esc(x)}</li>" for x in items if str(x).strip())

def _md_inline(s: str) -> str:
    """Render the inline **bold**/*italic* in our own authored applicability notes (no user input)."""
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s

def _render_authorities(auths, label: str):
    """Citation pills + a verbatim-trust line + a collapsible panel of the cited
    provisions, each badged verified (✓) or unverified (⚠) by the guardrail."""
    auths = [a for a in (auths or []) if isinstance(a, dict)
             and (str(a.get("source_text", "")).strip() or str(a.get("quote", "")).strip())]
    if not auths:
        return
    ntot = len(auths)
    nver = sum(1 for a in auths if a.get("verified"))
    if any("verified" in a for a in auths):
        if nver == ntot:
            st.markdown(
                f'<div class="lc-trust ok">✓ The {ntot} quoted passage(s) below are shown '
                f'verbatim from the Code — this confirms the wording, not the interpretation '
                f'above. Read the text to check it.</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="lc-trust warn">⚠ {ntot - nver} of {ntot} quote(s) could not be '
                f'matched to the Code text — treat those as unverified, and check the wording '
                f'below.</div>', unsafe_allow_html=True)
    pills = "".join(
        f'<span class="lc-cite">{_esc(a.get("citation") or "Provision")}</span>' for a in auths)
    st.markdown(
        f'<div class="lc-cite-row"><span class="lc-src-label">Authority</span>{pills}</div>',
        unsafe_allow_html=True)
    with st.expander(label, expanded=True):
        for a in auths:
            v = a.get("verified")
            badge = ('<span class="lc-verified">✓ verbatim</span>' if v
                     else '<span class="lc-unverified">⚠ unverified</span>' if v is False else '')
            cls = " unverified" if v is False else ""
            text = corpus._trim(a.get("source_text") or a.get("quote", ""))
            ttl = a.get("title")
            cite_html = _esc(a.get("citation") or "Provision")
            if ttl:
                cite_html += f' <span class="lc-auth-title">— {_esc(ttl)}</span>'
            st.markdown(
                f'<div class="lc-auth-cite">{cite_html} {badge}</div>'
                f'<blockquote class="lc-auth-quote{cls}">{_esc_ml(text)}</blockquote>',
                unsafe_allow_html=True)


def render_comparison(data: dict):
    """Render an old-Act ↔ new-Code comparison: headline, per-change old|new columns,
    an impact line, and the verbatim provisions."""
    hl = str(data.get("headline", "")).strip()
    if hl:
        st.markdown(f'<div class="lc-cmp-headline">🔄 {_esc(hl)}</div>', unsafe_allow_html=True)
    for ch in (data.get("changes") or []):
        if not isinstance(ch, dict):
            continue
        st.markdown(f'<div class="lc-cmp-topic">{_esc(ch.get("topic", "Change"))}</div>',
                    unsafe_allow_html=True)
        col_old, col_new = st.columns(2)
        with col_old:
            st.markdown(
                f'<div class="lc-cmp-card old"><div class="lc-cmp-tag old">◂ Previously</div>'
                f'<div class="lc-cmp-body">{_esc(ch.get("old", "—"))}</div>'
                f'<div class="lc-cmp-cite">{_esc(ch.get("old_cite", "")) or "—"}</div></div>',
                unsafe_allow_html=True)
        with col_new:
            st.markdown(
                f'<div class="lc-cmp-card new"><div class="lc-cmp-tag new">Now, in force ▸</div>'
                f'<div class="lc-cmp-body">{_esc(ch.get("new", "—"))}</div>'
                f'<div class="lc-cmp-cite">{_esc(ch.get("new_cite", "")) or "—"}</div></div>',
                unsafe_allow_html=True)
        impact = str(ch.get("impact", "")).strip()
        if impact:
            st.markdown(
                f'<div class="lc-cmp-impact"><span>What to do&nbsp;→</span> {_esc(impact)}</div>',
                unsafe_allow_html=True)
    _render_authorities(data.get("authorities"), "📜  Show statutory text (old & new)")
    st.markdown(f'<div class="lc-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)


_ISSUE_STATUS = {
    "ok":        ("✓", "ok"),
    "risk":      ("⚠", "risk"),
    "violation": ("✕", "violation"),
    "info":      ("›", "info"),
}

def _render_analysis(analysis: list):
    """Render the dissection: one card per legal issue — status chip, the issue, the reasoning
    (law applied to the manager's facts), and the governing provision."""
    st.markdown('<div class="lc-section-label">Analysis</div>', unsafe_allow_html=True)
    for a in analysis:
        icon, cls = _ISSUE_STATUS.get(str(a.get("status", "info")).lower(), _ISSUE_STATUS["info"])
        issue   = _esc(str(a.get("issue", "")).strip() or "Issue")
        finding = _esc(str(a.get("finding", "")).strip())
        cite    = str(a.get("citation", "")).strip()
        cite_html = f'<div class="lc-issue-cite">{_esc(cite)}</div>' if cite else ""
        st.markdown(
            f'<div class="lc-issue {cls}">'
            f'<div class="lc-issue-head"><span class="lc-issue-chip {cls}">{icon}</span>{issue}</div>'
            f'<div class="lc-issue-body">{finding}</div>'
            f'{cite_html}</div>',
            unsafe_allow_html=True,
        )


def render_answer(data: dict):
    """Render a structured answer as scannable cards (verdict / points / actions /
    collapsible authorities). Falls back to markdown for unstructured replies."""
    if isinstance(data, dict) and data.get("type") == "comparison" and "_raw" not in data:
        render_comparison(data)
        return
    if not isinstance(data, dict) or "_raw" in data:
        st.markdown(data.get("_raw", "") if isinstance(data, dict) else str(data))
        st.markdown(f'<div class="lc-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)
        return

    is_comp = data.get("type") == "compliance"
    verdict = data.get("verdict") or {}

    # 0 — Restatement (shows the situation was understood)
    restate = str(data.get("restatement", "")).strip()
    if restate:
        st.markdown(f'<div class="lc-restate">{_esc(restate)}</div>', unsafe_allow_html=True)

    # 1 — Verdict card (compliance) or lead paragraph (info, only when there's no analysis)
    status   = (verdict.get("status") or "").strip()
    analysis = [a for a in (data.get("analysis") or []) if isinstance(a, dict)
                and (str(a.get("issue", "")).strip() or str(a.get("finding", "")).strip())]
    if is_comp and status in _VERDICT:
        icon, label = _VERDICT[status]
        st.markdown(
            f'<div class="lc-verdict {status}">'
            f'<span class="lc-verdict-icon">{icon}</span>'
            f'<div class="lc-verdict-meta">'
            f'<div class="lc-verdict-title">{label}</div>'
            f'<div class="lc-verdict-text">{_esc(verdict.get("summary", ""))}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    elif not analysis and str(data.get("answer", "")).strip():
        st.markdown(f'<div class="lc-lead">{_esc(data["answer"])}</div>',
                    unsafe_allow_html=True)

    # 2 — Analysis: the dissection (issue → governing provision → application → per-issue status)
    if analysis:
        _render_analysis(analysis)
    else:
        # Backward-compat: older replies (and history) use requirements / key_points bullets
        points = (data.get("requirements") if is_comp else data.get("key_points")) or []
        points = [p for p in points if str(p).strip()]
        if points:
            label = "What the law requires" if is_comp else "Key points"
            st.markdown(
                f'<div class="lc-block"><div class="lc-section-label">{label}</div>'
                f'<ul class="lc-req">{_bullets(points)}</ul></div>',
                unsafe_allow_html=True,
            )

    # 3 — Action box (compliance, only when there are actions)
    actions = [a for a in (data.get("actions") or []) if str(a).strip()]
    if actions:
        st.markdown(
            f'<div class="lc-action"><div class="lc-section-label">What to do now</div>'
            f'<ul class="lc-action-list">{_bullets(actions)}</ul></div>',
            unsafe_allow_html=True,
        )

    # 3.5 — Applies-to-your-case: verified establishment-size / tenure thresholds
    applies = [n for n in (data.get("_applicability") or []) if str(n).strip()]
    if applies:
        items = "".join(f"<li>{_md_inline(n)}</li>" for n in applies)
        st.markdown(
            f'<div class="lc-applies"><div class="lc-section-label">Applies to your case</div>'
            f'<ul class="lc-applies-list">{items}</ul></div>',
            unsafe_allow_html=True,
        )

    # 4 — Authorities: citation pills + verbatim-verified collapsible text
    _render_authorities(data.get("authorities"), "📜  Show statutory text")

    # 5 — Disclaimer
    st.markdown(f'<div class="lc-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("messages", []),
    ("pending", None),
    ("force_compare", False),
    ("intake", None),          # active clarifying-questions card, or None
    ("skip_intake", False),    # the next pending query has already been through intake
    ("intake_got", None),      # facts gathered, for applicability after the answer
]:
    if key not in st.session_state:
        st.session_state[key] = default

def _submit(q: str):
    st.session_state.pending = q

def _submit_compare(q: str):
    """Re-ask the same question, forced into old-Act comparison mode."""
    st.session_state.pending = q
    st.session_state.force_compare = True

def _submit_explore(q: str):
    """Cross-reference chip: answer the related provision directly, never via the intake card."""
    st.session_state.pending = q
    st.session_state.skip_intake = True

def _clear_intake_widgets():
    """Drop the radio widget state so a later card never pre-fills a previous answer."""
    for k in [k for k in st.session_state if str(k).startswith("intake_")]:
        del st.session_state[k]

def _finalize_intake(skip: bool = False):
    """Fold the chosen clarifying answers into the query and send it on to be answered."""
    ik = st.session_state.intake
    if not ik:
        return
    got = {}
    if not skip:
        for fact in ik["needed"]:
            label = st.session_state.get(f"intake_{fact['key']}")
            val = next((c for (l, c) in fact["opts"] if l == label), None)
            if val:
                got[fact["key"]] = val
    _clear_intake_widgets()
    st.session_state.intake = None
    st.session_state.intake_got = got
    st.session_state.pending = ik["q"] + intake.clause(got)
    st.session_state.skip_intake = True

def _render_followups(query, cross, show_compare, key_prefix):
    """Cross-reference chips + the old-law comparison button, shown beneath an answer.
    Rendered from both the live turn and the history loop, so keys are prefixed per message."""
    if cross:
        st.markdown('<div class="lc-xref-label">Related provisions to check</div>',
                    unsafe_allow_html=True)
        cols = st.columns(2)
        for j, (label, q) in enumerate(cross):
            cols[j % 2].button(label, key=f"{key_prefix}_x{j}", on_click=_submit_explore, args=(q,))
    if show_compare:
        st.button("🔄  What changed from the old law?", key=f"{key_prefix}_chg",
                  on_click=_submit_compare, args=(query,))


# ─────────────────────────────────────────────────────────────────────────────
# ── HERO + SEARCH SECTION ────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
badges_html = "".join(
    f'<span class="lc-badge">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)

st.markdown(f"""
<div class="lc-hero">
  <div class="lc-hero-rule"></div>
  <div class="lc-hero-inner">
    <div class="lc-hero-circle">⚖</div>
    <div class="lc-eyebrow">
      <span class="lc-eyebrow-dot"></span>
      Indian Labour Codes
      <span class="lc-eyebrow-line"></span>
      HR Compliance Reference
    </div>
    <h1 class="lc-title">
      Labour Codes
      <span class="lc-title-em">Assistant</span>
    </h1>
    <p class="lc-sub">
      Ask about compliance, definitions, or obligations — grounded in the four
      Labour Codes with exact Section citations.
    </p>
    <div class="lc-badges">{badges_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Chat input — Streamlit always renders this in a sticky bottom dock ─────
if prompt := st.chat_input(
    "e.g. I retrenched an employee with 2 days notice — was that correct?"
):
    _submit(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# Auth warning
# ─────────────────────────────────────────────────────────────────────────────
if not _has_key():
    st.markdown(
        '<div class="lc-alert" style="margin-top:1.5rem;">'
        '⚙️ Add <strong>AWS_BEARER_TOKEN_BEDROCK</strong> and '
        '<strong>AWS_REGION</strong> in <em>App → Settings → Secrets</em> to activate.'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demo preview (visual check, no Bedrock needed):  add ?demo=1 to the URL
# ─────────────────────────────────────────────────────────────────────────────
def _demo_param():
    try:
        return st.query_params.get("demo")
    except Exception:
        return None

if _demo_param():
    _demo_samples = [
        {
            "type": "compliance",
            "restatement": "You let a worker with 3 years' service go for repeated late-coming, giving two days' notice and no compensation.",
            "verdict": {"status": "non-compliant",
                        "summary": "This is a retrenchment that skips the mandatory notice and compensation, so it is non-compliant."},
            "analysis": [
                {"issue": "Does ending this worker's service count as 'retrenchment'?",
                 "finding": "The worker has over one year of continuous service and is not being dismissed as punishment after an inquiry, so the exit is a retrenchment and the Section 70 safeguards apply in full.",
                 "status": "info",
                 "citation": "Section 70 — Industrial Relations Code, 2020"},
                {"issue": "Was the notice period valid?",
                 "finding": "Section 70 requires one month's written notice stating reasons, or wages in lieu. Two days' notice falls about 28 days short, so you must pay wages in lieu for the shortfall.",
                 "status": "violation",
                 "citation": "Section 70 — Industrial Relations Code, 2020"},
                {"issue": "Is retrenchment compensation owed?",
                 "finding": "Compensation of 15 days' average pay for every completed year is mandatory. For 3 completed years that is roughly 45 days' pay, which has not been paid.",
                 "status": "violation",
                 "citation": "Section 70 — Industrial Relations Code, 2020"},
            ],
            "actions": [
                "Pay wages in lieu for the ~28-day notice shortfall.",
                "Pay retrenchment compensation of 15 days' average pay × 3 completed years.",
                "File the prescribed notice of retrenchment with the appropriate Government.",
            ],
            "authorities": [
                {"citation": "Section 70 — Industrial Relations Code, 2020", "verified": True,
                 "quote": "No workman employed in any industrial establishment who has been in continuous service for not less than one year under an employer shall be retrenched until the workman has been given one month's notice in writing indicating the reasons for retrenchment and the period of notice has expired, or the workman has been paid in lieu of such notice, wages for the period of the notice."},
            ],
        },
        {
            "type": "comparison",
            "headline": "The threshold for needing Government permission to retrench rose from 100 to 300 workers.",
            "changes": [
                {"topic": "Government permission to retrench",
                 "old": "Establishments with 100 or more workmen needed prior Government permission to retrench.",
                 "old_cite": "Section 25N — Industrial Disputes Act, 1947",
                 "new": "The threshold is raised to 300 or more workers (Government may raise it further).",
                 "new_cite": "Section 65 — Industrial Relations Code, 2020",
                 "impact": "Establishments with 100–299 workers no longer need prior permission — but still owe notice and compensation."},
                {"topic": "Notice & compensation",
                 "old": "One month's notice (or wages in lieu) and 15 days' average pay per completed year.",
                 "old_cite": "Section 25F — Industrial Disputes Act, 1947",
                 "new": "Retained: one month's notice (or wages in lieu) and 15 days' wages per completed year.",
                 "new_cite": "Section 70 — Industrial Relations Code, 2020",
                 "impact": "No change here — keep paying notice + 15 days/year."},
            ],
            "authorities": [
                {"citation": "Section 25N — Industrial Disputes Act, 1947", "verified": True,
                 "quote": "No workman employed in any industrial establishment to which this Chapter applies, who has been in continuous service for not less than one year … shall be retrenched … until the prior permission of the appropriate Government … has been obtained …"},
                {"citation": "Section 65 — Industrial Relations Code, 2020", "verified": True,
                 "quote": "No worker employed in any industrial establishment to which this Chapter applies … shall be retrenched until the prior permission of the appropriate Government is obtained, where such establishment employed not less than three hundred workers …"},
            ],
        },
        {
            "type": "compliance",
            "_demo_topic": "retrench",
            "verdict": {"status": "non-compliant",
                        "summary": "One month's written notice (or wages in lieu) is required "
                                   "before retrenchment; two days is not enough."},
            "_applicability": intake.applicability(
                "retrench", {"size": "in an establishment employing 50 to 299 workers"}),
            "requirements": [
                "At least one month's written notice, or wages in lieu of the notice period.",
                "The notice must state the reasons for retrenchment.",
                "Retrenchment compensation of 15 days' average pay for every completed year.",
                "Notice to the appropriate Government in the prescribed manner.",
            ],
            "actions": [
                "Pay wages in lieu for the ~28-day shortfall in notice.",
                "Pay the retrenchment compensation due for completed years of service.",
                "File the prescribed notice with the appropriate Government.",
            ],
            "authorities": [
                {"citation": "Section 70 — Industrial Relations Code, 2020",
                 "quote": "No workman employed in any industrial establishment who has been in "
                          "continuous service for not less than one year under an employer shall "
                          "be retrenched until the workman has been given one month's notice in "
                          "writing indicating the reasons for retrenchment and the period of "
                          "notice has expired, or the workman has been paid in lieu of such "
                          "notice, wages for the period of the notice."},
            ],
        },
        {
            "type": "info",
            "answer": "Gratuity is a lump-sum reward for long service, payable when an employee "
                      "leaves after at least five years of continuous service. It is calculated "
                      "at fifteen days' wages for every completed year of service.",
            "key_points": [
                "Payable on resignation, retirement, superannuation, death or disablement.",
                "Five years' continuous service is required (waived for death or disablement).",
                "Calculated at 15 days' wages for each completed year of service.",
                "Fixed-term employees are paid pro rata, even under five years.",
            ],
            "authorities": [
                {"citation": "Section 53 — Code on Social Security, 2020",
                 "quote": "Gratuity shall be payable to an employee on the termination of his "
                          "employment after he has rendered continuous service for not less than "
                          "five years."},
            ],
        },
    ]
    st.markdown('<div class="lc-correction">🔍 Demo preview — sample answers (not live).</div>',
                unsafe_allow_html=True)
    for _i, _d in enumerate(_demo_samples):
        for _a in _d.get("authorities", []):       # show the new titles + verbatim badges in the no-key demo
            _a.setdefault("title", corpus.lookup_title(LOADED, _a.get("citation", "")))
            _a.setdefault("verified", True)
        with st.chat_message("assistant", avatar="⚖️"):
            _srcs = [a["citation"].split("—")[-1].strip() for a in _d["authorities"]]
            st.markdown(_src_row_html(_srcs, []), unsafe_allow_html=True)
            render_answer(_d)
            if _d.get("_demo_topic"):               # showcase the related-provision chips too
                _render_followups(None, intake.cross_refs(_d["_demo_topic"]), False, f"demo_{_i}")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Chat history
# ─────────────────────────────────────────────────────────────────────────────
for _i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="⚖️"):
            if msg.get("corrections"):
                st.markdown(_correction_html(msg["corrections"]), unsafe_allow_html=True)
            if msg.get("sources") or msg.get("no_provision"):
                st.markdown(
                    _src_row_html(msg.get("sources", []), msg.get("no_provision", [])),
                    unsafe_allow_html=True,
                )
            _d = msg.get("data") or {"_raw": msg.get("content", "")}
            render_answer(_d)
            _show_cmp = bool(msg.get("query") and msg.get("sources")
                             and isinstance(_d, dict) and _d.get("type") != "comparison"
                             and "_raw" not in _d)
            _render_followups(msg.get("query"), msg.get("cross") or [], _show_cmp, f"hist_{_i}")


# ─────────────────────────────────────────────────────────────────────────────
# Intake — a couple of one-tap clarifying questions when a scenario is missing decisive facts
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.intake and not st.session_state.pending:
    _ik = st.session_state.intake
    with st.chat_message("assistant", avatar="⚖️"):
        st.markdown(
            '<div class="lc-intake-head">A couple of quick details so the verdict is precise — '
            'or skip and I\'ll answer in general terms.</div>'
            f'<div class="lc-intake-q">“{_esc(_ik["q"])}”</div>',
            unsafe_allow_html=True)
        for _fact in _ik["needed"]:
            st.radio(_fact["q"], [o[0] for o in _fact["opts"]],
                     key=f"intake_{_fact['key']}", index=None, horizontal=True)
        _b1, _b2, _ = st.columns([1.1, 1.5, 2.4])
        _b1.button("Get my answer", type="primary", key="intake_go", on_click=_finalize_intake)
        _b2.button("Skip — answer generally", key="intake_skip",
                   on_click=_finalize_intake, args=(True,))


# ─────────────────────────────────────────────────────────────────────────────
# Sample questions (empty state)
# ─────────────────────────────────────────────────────────────────────────────
if (
    not st.session_state.messages
    and not st.session_state.pending
    and not st.session_state.intake
):
    st.markdown('<div class="lc-samples-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="lc-samples-label">Try asking</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="lc-samples-hint">Tip: include the specifics — years of service, notice '
        'given, number of workers, establishment type — and you\'ll get a precise, cited verdict.</div>',
        unsafe_allow_html=True)
    # Spread across the app's modes: a compliance verdict, a threshold scenario, a definition,
    # a calculation, an old-vs-new comparison, and a records/procedure question.
    samples = [
        "I retrenched an employee with 3 years' service on 2 days' notice — was that correct?",
        "We employ 120 workers and want to close a unit — what's the lawful process?",
        "How is 'wages' defined across the four Codes?",
        "When is gratuity payable and how is it calculated?",
        "What changed for retrenchment from the old Industrial Disputes Act?",
        "What registers and returns must an establishment maintain?",
    ]
    c1, c2 = st.columns(2)
    for i, s in enumerate(samples):
        (c1 if i % 2 == 0 else c2).button(s, key=f"s{i}", on_click=_submit, args=(s,))
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Process pending query
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.pending:
    # Intake first: a fresh compliance scenario that's missing a decisive fact (tenure, head-count,
    # reason) gets a short clarifying card; queries already through intake — or forced comparisons —
    # go straight to the answer.
    if st.session_state.skip_intake or st.session_state.force_compare:
        st.session_state.skip_intake = False
    elif (_needed := intake.screen(st.session_state.pending)):
        _clear_intake_widgets()
        st.session_state.intake = {"q": st.session_state.pending, "needed": _needed, "got": {}}
        st.session_state.pending = None
        st.rerun()

    st.session_state.intake = None     # about to answer — never leave a stale card on screen
    raw_q = st.session_state.pending
    st.session_state.pending = None

    corrected_q, corrections = corpus.correct_query(raw_q)

    # Show user message
    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    force_compare = st.session_state.force_compare
    st.session_state.force_compare = False

    with st.spinner("Searching the codes…"):
        extra_terms = analyze_query(raw_q)               # legal keywords; "" if offline/error
        # Route from the original query; the expansion only sharpens ranking and may add a
        # missed code — it can never knock the relevant code below the routing gate.
        all_results = corpus.search_all(LOADED, corrected_q, k=8, boost=extra_terms)

    sources      = [r["meta"]["short"] for r in all_results.values() if r["found"]]
    no_provision = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
    # Establishment-size / service gating, computed BEFORE the answer so the verdict respects the
    # threshold that decides which Chapter applies — then reused as the applicability box below.
    _topic = intake.topic(corrected_q)
    _got   = st.session_state.pop("intake_got", None)
    if _got is None:
        _got = intake.facts_from_query(corrected_q)
    _notes = intake.applicability(_topic, _got or {}) if _topic else []
    # Below 300 workers, keep Chapter X prior-permission Sections out of the grounding entirely
    # (filter a shallow copy so display/routing and the quote-verifier still see the full corpus;
    # comparison keeps them — it is about what changed).
    _excl = _excluded_ir_sections(_topic, _got or {})
    _ir   = all_results.get("ir")
    _rfp  = all_results
    if _excl and _ir and _ir.get("found"):
        _rfp = {**all_results,
                "ir": {**_ir, "chunks": [c for c in _ir["chunks"] if c.get("num") not in _excl]}}
    user_msg     = build_prompt(raw_q, _rfp, applicability=_notes)
    is_compare   = bool(sources) and (force_compare or _is_comparison(corrected_q))

    with st.chat_message("assistant", avatar="⚖️"):
        if corrections:
            st.markdown(_correction_html(corrections), unsafe_allow_html=True)

        if sources or no_provision:
            st.markdown(_src_row_html(sources, no_provision), unsafe_allow_html=True)

        if not sources:
            names = " · ".join(e["meta"]["short"] for e in LOADED.values())
            data  = {"_raw": (
                f"No relevant provisions found across **{names}** for this query. "
                "Try rephrasing or ask about a specific Section or topic."
            )}
        elif is_compare:
            with st.spinner("Comparing the old Act with the new Code…"):
                data = generate_comparison(build_comparison_prompt(corrected_q, all_results))
            data = _verify_quotes(data)
        else:
            with st.spinner("Analysing the statute…"):
                data = generate_answer([{"role": "user", "content": user_msg}])
            data = _verify_quotes(data)
        # Attach the (already-computed) size applicability + related-provision chips
        cross = []
        if isinstance(data, dict) and "_raw" not in data and not is_compare and _topic:
            if _notes:
                data["_applicability"] = _notes
            cross = intake.cross_refs(_topic)

        render_answer(data)
        _show_cmp = bool(sources and not is_compare and isinstance(data, dict) and "_raw" not in data)
        _render_followups(corrected_q, cross, _show_cmp, f"live_{len(st.session_state.messages)}")

    st.session_state.messages.append({
        "role":         "assistant",
        "data":         data,
        "query":        corrected_q,
        "sources":      sources,
        "no_provision": no_provision,
        "corrections":  corrections,
        "cross":        cross,
    })
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="lc-footer">'
    '<strong>HR Compliance Reference</strong>'
    f' &nbsp;·&nbsp; {_model_label()} via AWS Bedrock'
    ' &nbsp;·&nbsp; Always consult a qualified legal advisor'
    '</div>',
    unsafe_allow_html=True,
)
