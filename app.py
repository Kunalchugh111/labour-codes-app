"""
app.py — Labour Codes Assistant (Streamlit)
Backend : AWS Bedrock (Converse API) — mistral.mistral-large-3-675b-instruct
Auth    : AWS_BEARER_TOKEN_BEDROCK + AWS_REGION in Streamlit secrets
Design  : Legal editorial — deep navy, parchment, gold accent
"""

import hashlib
import hmac
import json
import os
import re
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
import streamlit as st

import corpus
import intake
import usage

# Mistral Large 3 — strongest model invokable on this account (Claude is blocked by an AWS
# Marketplace payment issue; Nova Pro flips borderline numeric verdicts). Gives more complete,
# accurate, appropriately-caveated legal answers. Override via the BEDROCK_MODEL_ID secret.
MODEL_ID = "mistral.mistral-large-3-675b-instruct"

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
  /* Modern AI-SaaS accent (periwinkle / indigo) + soft sky background */
  --indigo:        #4F5BD5;
  --indigo-2:      #6B78E6;
  --indigo-3:      #3A45B0;
  --indigo-bg:     #EEF1FD;
  --indigo-border: #D6DCF8;
  --sky-1:         #EAEFFB;
  --sky-2:         #C9D5F1;
  --sky-3:         #DCE4F6;
  --grad-indigo:   linear-gradient(135deg, #6B78E6 0%, #4F5BD5 55%, #5B6EE1 100%);
  /* repointed warm→cool so legacy "parchment" surfaces match the sky/indigo theme */
  --parchment:   #F4F7FE;
  --parchment-2: #ECF0FB;
  --parchment-3: #DFE5F5;
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
  /* Layered atmosphere: soft indigo + cyan glows floating over the base sky gradient give the
     page depth so the white content card reads as floating, not pasted on a flat fill. */
  background:
    radial-gradient(ellipse 64% 48% at 10% 6%,   rgba(91,110,225,.12), transparent 60%),
    radial-gradient(ellipse 58% 46% at 94% 94%,  rgba(86,194,214,.10), transparent 62%),
    radial-gradient(ellipse 50% 40% at 88% 4%,   rgba(124,107,232,.07), transparent 60%),
    linear-gradient(168deg, var(--sky-1) 0%, var(--sky-3) 46%, var(--sky-2) 100%) !important;
  background-attachment: fixed !important;
  font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
/* Premium touches: indigo text selection + a slim themed scrollbar. */
::selection { background: rgba(79,91,213,.18); color: var(--navy); }
* { scrollbar-width: thin; scrollbar-color: var(--slate-4) transparent; }
*::-webkit-scrollbar { width: 10px; height: 10px; }
*::-webkit-scrollbar-thumb {
  background: var(--slate-4); border-radius: 999px;
  border: 3px solid transparent; background-clip: content-box;
}
*::-webkit-scrollbar-thumb:hover { background: var(--slate-3); background-clip: content-box; }

/* ── Kill every piece of Streamlit chrome ─────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu, footer { display: none !important; }

/* ── Main content column — a floating white card on the sky gradient ───────── */
.main .block-container {
  max-width: 880px !important;
  background: var(--white);
  border-radius: 26px;
  box-shadow: 0 24px 70px rgba(40,55,120,.16), 0 2px 10px rgba(40,55,120,.06);
  padding: 0 2.25rem 9rem !important;
  margin: 2rem auto 2.5rem !important;
  overflow: hidden;
}

/* ══ CRITICAL: Fix the black bar at bottom ════════════════════════════════
   Root cause: Streamlit's stBottom uses a pseudo-element or child div that
   inherits a dark background from the app shell. We must override EVERY layer.
   ═════════════════════════════════════════════════════════════════════════ */
[data-testid="stBottom"] {
  background: transparent !important;
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
  background: transparent !important;
  background-color: transparent !important;
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
  background: transparent;
  margin: 0;
  padding: 0;
  position: relative;
  animation: fadeIn .6s var(--ease) both;
}

/* Slim header — shown once a conversation starts, so answers own the viewport */
.lc-hero-slim {
  display: flex; align-items: center; gap: 12px;
  background: var(--navy);
  margin: 0 -1.5rem 1.5rem;
  padding: 11px 1.5rem;
  border-bottom: 2px solid var(--indigo);
  animation: fadeIn .4s var(--ease) both;
}
.lc-hero-slim-mark {
  width: 30px; height: 30px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; border: 1px solid rgba(201,168,76,.45);
  color: var(--indigo-2); font-size: 15px;
}
.lc-hero-slim-name {
  font-family: 'Playfair Display', serif; font-size: 17px; font-weight: 700;
  color: #fff; letter-spacing: .01em;
}
.lc-hero-slim-name em { color: var(--indigo-2); font-style: italic; }
.lc-hero-slim-badges { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
@media (max-width: 560px) { .lc-hero-slim-badges { display: none; } }

/* soft indigo glow, top-right — airy, not a dark banner */
.lc-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 90% 70% at 115% -20%, rgba(91,110,225,.10) 0%, transparent 55%);
  pointer-events: none;
}

/* Decorative circles */
.lc-hero::after { content: none; }

.lc-hero-inner {
  position: relative;
  padding: 3rem .25rem 1.5rem;
}

.lc-hero-rule { display: none; }

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
  opacity: 0;
  pointer-events: none;
  display: none;
}

.lc-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .28em;
  text-transform: uppercase;
  color: var(--slate-2);
  opacity: .9;
  margin-bottom: 1.1rem;
}
.lc-eyebrow-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--indigo);
  animation: breathe 2.8s ease-in-out infinite;
}
.lc-eyebrow-line {
  width: 28px; height: 1px;
  background: linear-gradient(90deg, var(--indigo), transparent);
  opacity: .6;
}

.lc-title {
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: clamp(36px, 5.2vw, 54px);
  font-weight: 700;
  color: var(--ink);
  line-height: 1.08;
  letter-spacing: -.03em;
  margin-bottom: .1em;
}
.lc-title-em {
  font-style: normal;
  font-weight: 600;
  color: var(--indigo);
  display: block;
  font-size: 1em;
  letter-spacing: -.025em;
}

.lc-sub {
  font-size: 14px;
  font-weight: 400;
  color: var(--slate-2);
  line-height: 1.7;
  max-width: 460px;
  margin: 1rem 0 1.6rem;
  letter-spacing: .005em;
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
  color: var(--indigo-3);
  background: var(--indigo-bg);
  border: 1px solid var(--indigo-border);
  padding: 5px 12px;
  border-radius: 999px;
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

/* The search input — an elevated "command bar". On focus it lifts and gains a soft indigo
   glow ring (layered box-shadows + a low-alpha 2px border, which stay clean instead of
   colour-fringing the way a thin saturated/gradient border does). */
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"], .stBottomBlockContainer {
  overflow: visible !important;          /* let the focus lift/ring breathe */
}
[data-testid="stChatInput"] {
  position: relative !important;
  background: linear-gradient(180deg, #FFFFFF 0%, #FBFCFF 100%) !important;
  border: 1.5px solid var(--indigo-border) !important;
  border-radius: 18px !important;
  box-shadow: 0 16px 44px rgba(40,55,120,.16), 0 2px 6px rgba(40,55,120,.06) !important;
  transition: border-color .25s var(--ease), box-shadow .25s var(--ease),
              transform .25s var(--ease) !important;
}
[data-testid="stChatInput"]:focus-within {
  /* A soft, semi-transparent 2px border (blends with white → no harsh 1px colour-fringe)
     plus a layered glow ring + elevation. */
  border: 2px solid rgba(79,91,213,.45) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 0 0 4px rgba(79,91,213,.12),
              0 22px 56px rgba(79,91,213,.20) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
  font-size: 15px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 400 !important;
  line-height: 1.6 !important;
  padding: 15px 17px !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--slate-3) !important;
  font-style: italic !important;
  font-weight: 300 !important;
}

/* Send button — a circular gradient pill that lifts and glows on hover. The testid is on the
   button element itself, so target it directly (a descendant `button` never matches). */
button[data-testid="stChatInputSubmitButton"] {
  background: var(--grad-indigo) !important;
  border: none !important;
  border-radius: 50% !important;
  width: 40px !important; height: 40px !important;
  color: #fff !important;
  box-shadow: 0 6px 18px rgba(79,91,213,.40) !important;
  transition: filter .18s var(--ease), transform .18s var(--ease),
              box-shadow .18s var(--ease) !important;
}
button[data-testid="stChatInputSubmitButton"]:hover {
  filter: brightness(1.1) !important;
  transform: translateY(-1px) scale(1.06) !important;
  box-shadow: 0 9px 26px rgba(79,91,213,.52) !important;
}
button[data-testid="stChatInputSubmitButton"] svg {
  color: #fff !important; fill: #fff !important;
}

/* ══ SAMPLE QUESTIONS ═══════════════════════════════════════════════════════ */
.lc-samples-wrap {
  padding: 2rem 0 .5rem;
  animation: fadeUp .5s var(--ease) .1s both;
}
.lc-samples-label {
  display: flex; align-items: center; gap: 10px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--indigo);
  margin-bottom: .5rem;
}
.lc-samples-label::before { content: "✦"; font-size: 9px; opacity: .7; letter-spacing: 0; }
.lc-samples-label::after {
  content: ""; flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--indigo-border), transparent);
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
  border-color: var(--indigo-border) !important;
  border-left-color: var(--indigo) !important;
  color: var(--navy) !important;
  transform: translateX(4px) !important;
  box-shadow: var(--s2) !important;
}

/* Primary CTA — indigo gradient pill (matches the AI-SaaS reference) */
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"] {
  background: var(--grad-indigo) !important;
  color: #fff !important;
  border: none !important;
  border-left: none !important;
  border-radius: 999px !important;
  font-weight: 600 !important;
  text-align: center !important;
  box-shadow: 0 8px 22px rgba(79,91,213,.30) !important;
}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
  background: var(--grad-indigo) !important;
  filter: brightness(1.06) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 12px 30px rgba(79,91,213,.40) !important;
}

/* ══ ALERTS ═════════════════════════════════════════════════════════════════ */
.lc-alert {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: var(--indigo-bg);
  border-left: 3px solid var(--indigo);
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
  border-left: 3px solid var(--indigo);
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
  border-radius: 12px;
  margin-bottom: 18px;
  border: 1px solid;
  border-left-width: 4px;
  box-shadow: var(--s1);
  animation: fadeUp .35s var(--ease) both;
}
.lc-verdict-icon {
  font-size: 20px; flex-shrink: 0; line-height: 1;
  width: 42px; height: 42px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.65); box-shadow: var(--s1);
}
.lc-verdict-meta { flex: 1; }
.lc-verdict-title {
  font-size: 10px; font-weight: 800;
  letter-spacing: .18em; text-transform: uppercase;
  margin-bottom: 4px;
}
.lc-verdict-text { font-size: 14px; font-weight: 400; line-height: 1.55; }

/* Subtle status gradient (tint → white) reads richer than a flat fill. */
.lc-verdict.compliant     { background: linear-gradient(135deg, var(--green-bg) 0%, #fff 130%); border-color: var(--green-b); color: var(--green); }
.lc-verdict.non-compliant { background: linear-gradient(135deg, var(--red-bg) 0%, #fff 130%);   border-color: var(--red-b);   color: var(--red); }
.lc-verdict.partial       { background: linear-gradient(135deg, var(--amber-bg) 0%, #fff 130%); border-color: var(--amber-b); color: var(--amber); }

/* ══ RESTATEMENT + ANALYSIS (the dissection) ════════════════════════════════ */
.lc-answer {
  background: linear-gradient(180deg, var(--white) 0%, var(--parchment) 140%);
  border: 1px solid var(--indigo-border); border-left: 4px solid var(--indigo);
  border-radius: 12px; padding: 16px 20px 17px; margin-bottom: 16px;
  box-shadow: var(--s1);
  animation: fadeUp .35s var(--ease) both;
}
.lc-answer-label {
  font-size: 10px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
  color: var(--slate-2); margin-bottom: 7px;
}
.lc-answer-text { font-size: 16.5px; font-weight: 600; line-height: 1.55; color: var(--navy); }
.lc-answer-cite {
  font-family: 'Playfair Display', serif; font-style: italic;
  font-size: 13px; font-weight: 600; color: var(--slate-2); margin-top: 9px;
}
.lc-restate {
  font-size: 12.5px; line-height: 1.55; color: var(--slate-3); font-style: italic;
  margin: 0 0 14px; padding-left: 12px; border-left: 2px solid var(--slate-5);
  opacity: .9; animation: fadeUp .3s var(--ease) both;
}
.lc-issue {
  border: 1px solid var(--slate-5); border-left-width: 3px; border-radius: 12px;
  padding: 14px 18px; margin-bottom: 11px; background: var(--white);
  box-shadow: var(--s1);
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
  font-size: 10px; font-weight: 800; letter-spacing: .18em;
  text-transform: uppercase; color: var(--indigo); margin-bottom: 9px;
}
.lc-lead {
  font-size: 15px; line-height: 1.75; color: var(--ink-2); font-weight: 400;
  margin-bottom: 18px; padding: 2px 0 2px 16px;
  border-left: 3px solid var(--navy-3);
  animation: fadeUp .35s var(--ease) both;
}
ul.lc-req, ul.lc-action-list { list-style: none; padding-left: 0 !important; margin: 0 !important; }
ul.lc-req li {
  position: relative; padding-left: 28px; margin-bottom: 10px;
  font-size: 14px; line-height: 1.6; color: var(--ink-2); font-weight: 400;
}
ul.lc-req li::before {
  content: "✓"; position: absolute; left: 0; top: 1px;
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--green-bg); border: 1px solid var(--green-b);
  color: var(--green); font-weight: 700; font-size: 10px; line-height: 1;
}
.lc-action {
  background: var(--indigo-bg); border: 1px solid var(--indigo-border);
  border-radius: 10px; padding: 15px 20px; margin-bottom: 18px;
  animation: fadeUp .35s var(--ease) both;
}
.lc-action .lc-section-label { color: var(--amber); }
ul.lc-action-list li {
  position: relative; padding-left: 28px; margin-bottom: 9px;
  font-size: 14px; line-height: 1.6; color: var(--ink-2); font-weight: 500;
}
ul.lc-action-list li::before {
  content: "→"; position: absolute; left: 0; top: 1px;
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--white); border: 1px solid var(--indigo-border);
  color: var(--indigo); font-weight: 700; font-size: 11px; line-height: 1;
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

/* Pipeline progress pill — the chevron-free st.status replacement */
.lc-stage {
  display: inline-flex; align-items: center; gap: 10px;
  font-size: 12.5px; font-weight: 600; letter-spacing: .01em;
  color: var(--indigo-3); background: var(--indigo-bg);
  border: 1px solid var(--indigo-border); border-radius: 999px;
  padding: 8px 18px; margin: 2px 0 10px;
  animation: fadeIn .25s var(--ease) both;
}
.lc-stage-dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--indigo);
  flex: 0 0 auto; animation: breathe 1.5s ease-in-out infinite;
}

/* Intake clarifying card + cross-reference chips */
.lc-intake-label {
  display: flex; align-items: center; gap: 10px;
  font-size: 10px; font-weight: 800; letter-spacing: .18em; text-transform: uppercase;
  color: var(--indigo); margin-bottom: 9px;
}
.lc-intake-label::before { content: "✦"; font-size: 9px; opacity: .7; letter-spacing: 0; }
.lc-intake-label::after {
  content: ""; flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--indigo-border), transparent);
}
.lc-intake-head { font-size: 14.5px; font-weight: 600; color: var(--ink-2); margin-bottom: 6px; }
.lc-intake-q {
  font-family: 'Playfair Display', serif; font-style: italic;
  color: var(--slate-3); font-size: 13.5px; margin-bottom: 4px;
}

/* The clarifying card itself: a designed panel instead of bare widgets. */
[class*="st-key-intake_card"] {
  background: linear-gradient(135deg, var(--white) 0%, var(--parchment) 130%);
  border: 1px solid var(--indigo-border);
  border-left: 3px solid var(--indigo-2);
  border-radius: 14px;
  padding: 18px 20px 16px;
  box-shadow: var(--s1);
  animation: fadeUp .35s var(--ease) both;
}
/* Each question's label -> small-caps eyebrow */
[class*="st-key-intake_card"] [data-testid="stWidgetLabel"] p {
  font-size: 10px !important; font-weight: 800 !important;
  letter-spacing: .14em !important; text-transform: uppercase !important;
  color: var(--slate-2) !important;
}
/* Options -> selectable pill chips (hide baseweb's radio circle; select via :has) */
[class*="st-key-intake_card"] [role="radiogroup"] {
  gap: 8px !important; flex-wrap: wrap !important; padding-bottom: 4px;
}
[class*="st-key-intake_card"] label[data-baseweb="radio"] {
  background: var(--white);
  border: 1px solid var(--slate-5);
  border-radius: 999px;
  padding: 7px 15px !important;
  margin: 0 !important;
  box-shadow: var(--s1);
  cursor: pointer;
  transition: border-color .18s var(--ease), background .18s var(--ease),
              transform .18s var(--ease), box-shadow .18s var(--ease);
}
[class*="st-key-intake_card"] label[data-baseweb="radio"] > div:first-child {
  display: none !important;              /* the radio circle — the pill IS the control */
}
[class*="st-key-intake_card"] label[data-baseweb="radio"] p {
  font-size: 12.5px !important; font-weight: 500 !important; color: var(--ink-2) !important;
}
[class*="st-key-intake_card"] label[data-baseweb="radio"]:hover {
  border-color: var(--indigo) !important;
  background: var(--indigo-bg);
  transform: translateY(-1px);
  box-shadow: var(--s2);
}
[class*="st-key-intake_card"] label[data-baseweb="radio"]:has(input:checked) {
  background: var(--grad-indigo);
  border-color: var(--indigo);
  box-shadow: 0 4px 14px rgba(79,91,213,.30);
}
[class*="st-key-intake_card"] label[data-baseweb="radio"]:has(input:checked) p {
  color: #fff !important; font-weight: 600 !important;
}
[class*="st-key-intake_go"] button { white-space: nowrap !important; }
/* Skip -> a quiet ghost link beside the primary CTA */
[class*="st-key-intake_skip"] button {
  white-space: nowrap !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: var(--slate-2) !important;
  font-size: 12.5px !important;
  text-decoration: underline dotted var(--slate-4) !important;
  text-underline-offset: 4px !important;
  padding: 12px 6px !important;
}
[class*="st-key-intake_skip"] button:hover {
  color: var(--indigo) !important;
  background: transparent !important;
  transform: none !important;
  border: none !important;
}
.lc-xref-label {
  display: flex; align-items: center; gap: 10px;
  font-size: 10px; font-weight: 800; letter-spacing: .18em; text-transform: uppercase;
  color: var(--indigo); margin: 22px 0 11px;
}
.lc-xref-label::before {
  content: "✦"; font-size: 9px; opacity: .7; letter-spacing: 0;
}
.lc-xref-label::after {              /* hairline rule trailing the label */
  content: ""; flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--indigo-border), transparent);
}

/* ── Follow-up suggestion tiles ──────────────────────────────────────────────
   Targeted via the keyed-container class so only these tiles get the treatment,
   not every st.button. Equal specificity to .stButton>button, declared later so
   it wins on source order. */
[class*="st-key-fupwrap_"] button {
  background: linear-gradient(135deg, var(--white) 0%, var(--parchment) 100%) !important;
  border: 1px solid var(--indigo-border) !important;
  border-left: 3px solid var(--indigo-2) !important;
  border-radius: 13px !important;
  padding: 14px 40px 14px 17px !important;   /* right room for the arrow */
  color: var(--navy) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  line-height: 1.5 !important;
  position: relative !important;
  box-shadow: var(--s1) !important;
  transition: transform .2s var(--ease), box-shadow .2s var(--ease),
              border-color .2s var(--ease), background .2s var(--ease) !important;
}
[class*="st-key-fupwrap_"] button::after {   /* arrow affordance */
  content: "→";
  position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
  color: var(--indigo); font-size: 14px; font-weight: 700; opacity: .5;
  transition: right .2s var(--ease), opacity .2s var(--ease);
}
[class*="st-key-fupwrap_"] button:hover {
  background: linear-gradient(135deg, var(--indigo-bg) 0%, var(--parchment-2) 100%) !important;
  border-color: var(--indigo) !important;
  border-left-color: var(--indigo) !important;
  color: var(--navy) !important;
  transform: translateY(-2px) !important;
  box-shadow: var(--s2) !important;
}
[class*="st-key-fupwrap_"] button:hover::after {
  opacity: 1; right: 13px;
}

/* "What changed from the old law?" — a centered ghost pill, set apart from the tiles */
[class*="st-key-fupchg_"] button {
  background: var(--indigo-bg) !important;
  border: 1px solid var(--indigo-border) !important;
  border-left: 1px solid var(--indigo-border) !important;
  border-radius: 999px !important;
  padding: 9px 20px !important;
  color: var(--indigo-3) !important;
  font-size: 12.5px !important;
  font-weight: 600 !important;
  text-align: center !important;
  width: auto !important;
  box-shadow: none !important;
  margin-top: 6px !important;
  transition: all .2s var(--ease) !important;
}
[class*="st-key-fupchg_"] button:hover {
  background: var(--indigo) !important;
  border-color: var(--indigo) !important;
  color: #fff !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 18px rgba(79,91,213,.25) !important;
}

/* Citation pills */
.lc-cite-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0 2px;
}
.lc-cite {
  font-size: 11px; font-weight: 600; letter-spacing: .02em;
  color: var(--navy); background: var(--indigo-bg);
  border: 1px solid var(--indigo-border); padding: 4px 11px; border-radius: 999px;
  white-space: nowrap; flex: 0 0 auto;
}

/* Collapsible statutory text */
[data-testid="stExpander"] {
  border: 1px solid var(--indigo-border) !important; border-radius: 12px !important;
  background: var(--white) !important; margin: 10px 0 4px !important;
  box-shadow: var(--s1) !important; overflow: hidden !important;
  transition: box-shadow .2s var(--ease), border-color .2s var(--ease),
              transform .2s var(--ease) !important;
}
[data-testid="stExpander"]:hover {
  border-color: var(--indigo) !important;
  box-shadow: var(--s2) !important;
  transform: translateY(-1px) !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary,
[data-testid="stExpander"] [data-testid="stExpanderToggle"] {
  font-size: 12px !important; font-weight: 700 !important;
  color: var(--indigo) !important; letter-spacing: .04em !important;
}
[data-testid="stExpander"] summary:hover { background: var(--indigo-bg) !important; }
.lc-auth-cite {
  font-family: 'Playfair Display', serif; font-size: 13.5px; font-weight: 700;
  color: var(--navy); margin: 12px 0 5px;
}
.lc-auth-cite:first-child { margin-top: 2px; }
.lc-auth-title { font-family: 'DM Sans', sans-serif; font-weight: 600; font-style: italic;
  color: var(--ink-soft, #5b6472); }
blockquote.lc-auth-quote {
  border-left: 3px solid var(--indigo); background: var(--indigo-bg);
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
  color: var(--navy); background: var(--indigo-bg); border: 1px solid var(--indigo-border);
  border-radius: 10px; padding: 13px 18px; margin-bottom: 18px; line-height: 1.5;
}
.lc-cmp-empty {
  font-size: 13.5px; line-height: 1.6; color: var(--slate-3);
  background: var(--indigo-bg); border: 1px solid var(--indigo-border);
  border-radius: 10px; padding: 13px 18px; margin-bottom: 14px;
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
  background: var(--indigo-bg); border-left: 3px solid var(--indigo);
  border-radius: 0 8px 8px 0; padding: 9px 14px; margin: 10px 0 22px;
}
.lc-cmp-impact span { color: var(--amber); font-weight: 700; }

/* ══ VERBATIM-QUOTE GUARDRAIL ════════════════════════════════════════════════ */
.lc-trust {
  font-size: 11.5px; font-weight: 600; letter-spacing: .01em; line-height: 1.55;
  border-radius: 10px; padding: 10px 14px; margin: 10px 0 4px;
  border-left-width: 3px !important;
}
.lc-trust.ok   { color: var(--green); background: var(--green-bg); border: 1px solid var(--green-b); border-left-color: var(--green); }
.lc-trust.warn { color: var(--red);   background: var(--red-bg);   border: 1px solid var(--red-b); border-left-color: var(--red); }
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

/* ══ SIGN-IN + ACCOUNT ROW ══════════════════════════════════════════════════ */
[class*="st-key-login_card"] {
  background: linear-gradient(135deg, var(--white) 0%, var(--parchment) 130%);
  border: 1px solid var(--indigo-border);
  border-left: 3px solid var(--indigo-2);
  border-radius: 14px;
  padding: 20px 22px 18px;
  margin-top: 1rem;
  max-width: 430px;
  box-shadow: var(--s2);
  animation: fadeUp .35s var(--ease) both;
}
[class*="st-key-login_card"] [data-testid="stWidgetLabel"] p {
  font-size: 10px !important; font-weight: 800 !important;
  letter-spacing: .14em !important; text-transform: uppercase !important;
  color: var(--slate-2) !important;
}
/* The form itself is invisible chrome — the card provides the frame */
[class*="st-key-login_card"] [data-testid="stForm"] {
  border: none !important; padding: 0 !important; margin: 0 !important;
  background: transparent !important; box-shadow: none !important;
}
/* ONE clean border on the outer baseweb wrapper; kill every inner border/background so
   the field can't double-frame (Streamlit nests input containers). */
[class*="st-key-login_card"] [data-baseweb="input"] {
  border: 1.5px solid var(--slate-4) !important;
  border-radius: 11px !important;
  background: var(--white) !important;
  overflow: hidden !important;
  transition: border-color .18s var(--ease), box-shadow .18s var(--ease) !important;
}
[class*="st-key-login_card"] [data-baseweb="input"] > div,
[class*="st-key-login_card"] [data-baseweb="base-input"] {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}
[class*="st-key-login_card"] input {
  font-family: 'DM Sans', sans-serif !important;
  font-size: 14.5px !important;
  color: var(--ink) !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 11px 14px !important;
}
[class*="st-key-login_card"] input::placeholder {
  color: var(--slate-3) !important; font-style: italic !important; font-weight: 300 !important;
}
[class*="st-key-login_card"] [data-baseweb="input"]:focus-within {
  border-color: var(--indigo) !important;
  box-shadow: 0 0 0 4px rgba(79,91,213,.13) !important;
}
/* Streamlit's "Press Enter to submit form" hint collides with the eye icon — drop it */
[class*="st-key-login_card"] [data-testid="InputInstructions"] {
  display: none !important;
}
/* The show/hide-password eye — quiet slate, indigo on hover */
[class*="st-key-login_card"] [data-baseweb="input"] button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--slate-3) !important; margin-right: 6px !important;
}
[class*="st-key-login_card"] [data-baseweb="input"] button:hover {
  color: var(--indigo) !important; background: transparent !important;
}
[class*="st-key-login_card"] [data-baseweb="input"] button svg {
  fill: currentColor !important;
}
/* Full-width gradient submit — same pill language as the rest of the app */
[class*="st-key-login_card"] [data-testid="stFormSubmitButton"] button {
  width: 100% !important;
  background: var(--grad-indigo) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 999px !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  letter-spacing: .02em !important;
  padding: 11px 0 !important;
  margin-top: 4px !important;
  text-align: center !important;
  box-shadow: 0 8px 22px rgba(79,91,213,.30) !important;
  transition: filter .18s var(--ease), transform .18s var(--ease),
              box-shadow .18s var(--ease) !important;
}
[class*="st-key-login_card"] [data-testid="stFormSubmitButton"] button:hover {
  filter: brightness(1.07) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 12px 30px rgba(79,91,213,.42) !important;
}
.lc-auth-fail {
  font-size: 12.5px; font-weight: 600; color: var(--red);
  background: var(--red-bg); border: 1px solid var(--red-b);
  border-left-width: 3px; border-radius: 8px;
  padding: 8px 12px; margin-top: 10px;
  animation: fadeIn .25s ease both;
}
.lc-account {
  display: inline-flex; align-items: center; gap: 9px;
  font-size: 13px; color: var(--slate);
  padding: 7px 2px 0;
}
.lc-account strong { color: var(--navy); font-weight: 600; }
.lc-account-n {
  font-size: 10.5px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
  color: var(--indigo-3); background: var(--indigo-bg);
  border: 1px solid var(--indigo-border);
  padding: 3px 10px; border-radius: 999px; white-space: nowrap;
}
[class*="st-key-logout_wrap"] button {
  background: transparent !important;
  border: 1px solid var(--slate-4) !important;
  border-left: 1px solid var(--slate-4) !important;
  border-radius: 999px !important;
  color: var(--slate-2) !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  padding: 6px 16px !important;
  width: auto !important;
  box-shadow: none !important;
  text-align: center !important;
}
[class*="st-key-logout_wrap"] button:hover {
  border-color: var(--red) !important;
  color: var(--red) !important;
  background: var(--red-bg) !important;
  transform: none !important;
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
  border-left: 3px solid var(--indigo) !important;
  margin: 1rem 0 !important;
  padding: 10px 0 10px 18px !important;
  color: var(--ink-2) !important;
  font-style: normal !important;
  font-size: 13.5px !important;
  background: var(--indigo-bg) !important;
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
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--slate-2);
  margin-right: 3px;
}
.lc-src-chip {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--white);
  background: linear-gradient(135deg, var(--navy-3) 0%, var(--navy) 100%);
  padding: 4px 12px;
  border-radius: 999px;
  box-shadow: var(--s1);
  white-space: nowrap;
  flex: 0 0 auto;
}
.lc-none-chip {
  font-size: 10px;
  color: var(--slate-3);
  background: var(--parchment-2);
  border: 1px solid var(--slate-5);
  padding: 4px 11px;
  border-radius: 4px;
  font-style: italic;
  white-space: nowrap;
  flex: 0 0 auto;
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
    cfg, data = corpus.load_corpus()
    corpus.warm(data)   # pre-build norm + citation index so the first answer doesn't stall
    return cfg, data

CFG, CORPUS_DATA = get_corpus()
# Use the cached object directly (not a per-rerun dict() copy): corpus.full_corpus_norm/_index
# memoise on id(corpus_dict), so a fresh id every rerun meant those caches never hit and grew one
# stale entry per rerun. Nothing mutates LOADED at the top level (the Chapter-X filter copies).
LOADED = CORPUS_DATA


@st.cache_resource
def _enable_semantic():
    """Load the prebuilt embedding index for hybrid (keyword + semantic) retrieval.
    Fail-soft: if the index or numpy is unavailable the app stays on keyword search."""
    try:
        import embeddings
        return embeddings.enable(LOADED)
    except Exception:
        return False

SEMANTIC_ON = _enable_semantic()

# Embeddings-first retrieval: when the semantic index is available, rank by the max-pooled
# sub-section embeddings (paraphrase-robust — benchmarked clearly above keyword and reranker on
# hard paraphrase/deep-clause queries). Fall back to keyword search when no index/key is present,
# so the app stays robust offline. Overridable via the RETRIEVAL_MODE env var.
_RMODE = os.environ.get("RETRIEVAL_MODE", "embeddings_primary" if SEMANTIC_ON else "lexical")
# In the embeddings-first modes, retire the two keyword "crutches" the embedding ranker makes
# redundant and can mis-rank against — the §2 definitions ×0.5 penalty and the forced Rules-slot
# reservation (benchmarked neutral on the hard + saturated sets). Keep the purely-additive
# _CODE_ANCHORS routing net. Lexical mode (the fallback) keeps all crutches as its ranking aids.
if _RMODE == "lexical":
    corpus.set_config(corpus.RetrievalConfig(mode="lexical"))
else:
    corpus.set_config(corpus.RetrievalConfig(mode=_RMODE, use_s2_penalty=False, reserve_rules=False))


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
# Sign-in + usage tracking
# ─────────────────────────────────────────────────────────────────────────────
# Accounts live in Streamlit secrets — add a [users] table (username = password) and,
# optionally, an `admins` list of usernames who can open the usage panel:
#
#   admins = ["rohit"]
#   [users]
#   rohit  = "some-password"                 # plaintext, or…
#   priya  = "d74ff0ee8da3b98065b02..."      # …a sha256 hex digest of the password
#
# With no [users] table the app runs open (no sign-in) — so a fresh clone still works.
try:                                          # secrets file may not exist at all (bare mode)
    if st.secrets.get("USAGE_DB"):
        os.environ["USAGE_DB"] = str(st.secrets["USAGE_DB"])
except Exception:
    pass


def _auth_users() -> dict:
    """The [users] table, keeping only string-valued entries. An email key someone forgot
    to quote ('a@b.com = "pw"' instead of '"a@b.com" = "pw"') parses as a NESTED TOML
    table, not a string — skip those so one bad line can't lock every user out."""
    try:
        return {str(k): v for k, v in dict(st.secrets.get("users", {})).items()
                if isinstance(v, str)}
    except Exception:
        return {}


def _resolve_user(identifier: str, users: dict):
    """Map what the visitor typed to the canonical [users] key, or None. Whitespace is
    trimmed and matching is case-insensitive (emails ARE case-insensitive, and visitors
    type 'Priya@Gmail.com'); the canonical key is returned so usage counts aggregate
    under one spelling."""
    ident = str(identifier or "").strip()
    if not ident:
        return None
    if ident in users:
        return ident
    low = ident.lower()
    return next((k for k in users if k.lower() == low), None)


def _admins() -> list:
    try:
        return [str(a) for a in st.secrets.get("admins", [])]
    except Exception:
        return []


def _password_ok(stored, given) -> bool:
    """Constant-time check. A 64-hex stored value is treated as sha256(password);
    anything else is compared as plaintext (secrets are already private)."""
    stored, given = str(stored or ""), str(given or "")
    if not stored:
        return False
    if re.fullmatch(r"[0-9a-fA-F]{64}", stored):
        return hmac.compare_digest(stored.lower(),
                                   hashlib.sha256(given.encode()).hexdigest())
    return hmac.compare_digest(stored, given)


def _current_user() -> str:
    return st.session_state.get("auth_user") or "anonymous"


_IST = ZoneInfo("Asia/Kolkata")


def _fmt_ts(ts) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(float(ts), _IST).strftime("%d %b %Y, %H:%M")


def _usage_csvs() -> tuple[str, str]:
    """(summary_csv, activity_csv) for the admin download buttons: the per-user rollup
    and the complete event log, Excel-friendly."""
    import csv
    import io
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(["user", "questions", "logins", "last_activity"])
    for r in usage.stats():
        w.writerow([r["user"], r["questions"], r["logins"], _fmt_ts(r["last_seen"])])
    a = io.StringIO()
    w = csv.writer(a)
    w.writerow(["when", "user", "event", "question"])
    for e in usage.all_events():
        w.writerow([_fmt_ts(e["ts"]), e["user"], e["event"], e["detail"]])
    return s.getvalue(), a.getvalue()


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
  "direct_answer": "for an 'info' question ONLY: ONE plain-English sentence that DIRECTLY answers it, leading with the figure/period/rule a non-lawyer wants (e.g. 'Wages must be paid by the 7th of the following month.'). No section numbers or legalese here — the citation is carried separately. null for compliance.",
  "verdict": {"status": "compliant" | "non-compliant" | "partial", "summary": "one-sentence bottom line"},
  "analysis": [
    {
      "issue": "the specific legal question this situation raises (short)",
      "finding": "2-4 sentences: what the governing provision requires AND how it applies to THESE facts",
      "status": "ok" | "risk" | "violation" | "info",
      "citation": "ONE provision only — e.g. \"Section 70 — Industrial Relations Code, 2020\" OR \"Rule 51 — Code on Wages (Central) Rules, 2020\""
    }
  ],
  "actions": ["imperative step the manager must take now", ...],
  "authorities": [{"citation": "ONE provision (a Section OR a Rule) — never combined", "quote": "exact statutory text"}],
  "follow_ups": ["3-4 short natural questions the manager would plausibly ask NEXT", ...]
}

Field rules:
- ALWAYS fill "restatement" and "analysis". "analysis" is the heart of the answer: surface EVERY
  distinct legal point the situation raises — as many issues as it genuinely needs (a simple lookup
  may be 1-2; a real compliance or procedural scenario is often 3-7+). Each issue spots one legal
  question, names exactly ONE governing provision, and APPLIES it to the manager's facts (not a
  generic summary). Order issues from most to least important.
- BE COMPREHENSIVE — this is a professional reference tool. Cite EVERY relevant provision across all
  applicable Codes: each governing Section AND each Central Rule that prescribes its procedure, form,
  register, timeline or rate, each as its OWN issue + authority. Do not stop at the single most
  obvious Section; an HR manager needs the full picture (e.g. a closure may involve §77 applicability,
  §79/§80 permission, §70 compensation, plus the Rules that prescribe the forms and notices).
- type "compliance": fill "verdict"; each issue "status" is "ok" (the stated facts satisfy the
  provision) / "risk" (the provision applies but the stated facts do NOT show whether it was met —
  open/conditional) / "violation" (the stated facts AFFIRMATIVELY show it was NOT met); fill
  "actions" with concrete next steps (only when NOT fully compliant, else []).
- verdict.status MUST match the WORST issue, never overstate: if any issue is "violation" →
  "non-compliant"; else if any issue is "risk" → "partial"; only when EVERY issue is "ok" →
  "compliant". A "compliant" verdict with a risk/violation issue or any outstanding action is wrong.
- type "info": set "verdict" to null; each issue "status" is "info"; "actions" may list helpful next
  steps or be []. ALSO fill "direct_answer" — one plain-English sentence that answers the question
  head-on, leading with the concrete figure/period/threshold (e.g. "A woman is entitled to up to 26
  weeks of paid maternity leave."). Put NO section numbers in it; if the supplied text does not
  contain the answer, say so there plainly ("The supplied Codes don't state this rate.").
- ALWAYS fill "follow_ups" with 3-4 SHORT, natural questions the same manager would plausibly ask
  next, specific to this topic and the four Codes (e.g. after a retrenchment verdict: "How much
  retrenchment compensation is due?", "Do we need government permission?", "What notice must we
  give?"). Each must be a self-contained question this assistant can answer; no numbering, ≤12 words.
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
- ONE PROVISION PER CITATION. Every "citation" names exactly ONE Section OR ONE Rule — NEVER combine
  them with "/" or ";" (e.g. write "Section 50 — Code on Wages, 2019" and, as a SEPARATE issue,
  "Rule 51 — Code on Wages (Central) Rules, 2020"). Combined citations break the verbatim-text lookup,
  so the Rule's text would silently vanish from the answer.
- When a Central Rule prescribes the procedure, forms, timelines, registers or rates for a Section you
  rely on, ADD A SEPARATE analysis issue for that Rule (and a separate authorities entry) — so both
  the Section AND the Rule appear with their own verbatim text. Procedural/registers/forms answers
  should lean on the Rules.
- Every "analysis[].citation" MUST also appear in "authorities" with its VERBATIM quote.
- Each supplied excerpt is headed with its provision title (e.g. "Section 9 — Power to fix floor
  wage"). Refer to provisions by that title in your finding so it reads naturally, but keep each
  "citation" in the exact one-provision "Section X — [Code Name]" / "Rule Y — [Rules Name]" form.

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
  "restatement" (and in "direct_answer" for an info question / "verdict.summary" for a compliance
  question — an info answer's "verdict" is null, so do not rely on it there).
- If the supplied text answers only PART of the question, answer that part fully and state plainly
  what the supplied provisions do NOT cover — never close the gap with outside knowledge or a guess.
- A rate/figure set by a SCHEME or by GOVERNMENT NOTIFICATION (e.g. the Provident Fund contribution
  rate, ESI rates) often is NOT stated in full in the Code itself — the Code gives the enabling
  Section and a base figure (e.g. Code on Social Security §16: contribution "ten per cent … or such
  other rate as may be notified"). Give the Section and the figure it actually states, then say the
  operative rate is fixed by the scheme/notification and is not in the supplied text. Do NOT invent a
  number and do NOT fall back to a repealed Act for it.
- STITCH related provisions across Codes when the question needs both. Money taken from an employee's
  pay has TWO legal questions: (1) the RATE/entitlement (e.g. PF contribution — Code on Social
  Security §16) and (2) whether it is a permitted DEDUCTION from wages (Code on Wages §18 lists the
  authorised deductions, which include PF/contributions to any fund). When the manager asks about a
  "deduction" for such an item, address BOTH — name the rate provision AND the deduction-authority
  provision — rather than answering from only one.
- DEFINITION questions ("what is X" / "define X"): give the statutory definition ONLY if the supplied
  text actually contains it (look for the "X" means … clause, usually in Section 2, or an operative
  definition in the relevant Section). Quote/paraphrase that text and cite it. If no supplied excerpt
  defines the term, say so plainly ("'X' is not a defined term in the supplied provisions") — do NOT
  supply a dictionary or common-usage meaning ("a token of appreciation", "commonly understood to
  mean…"). A plausible-sounding invented definition is worse than admitting it is not defined.
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
  EXCEPTION — when the supplied grounding is organised into "### TOPIC:" blocks (a broad
  "what changed overall" question), give ONE change per topic whose old and new texts actually
  differ, in the order the topics appear; more than 4 changes is expected there.
- LEAD with the change to the topic's CORE substantive rule (eligibility, amount/rate, threshold,
  notice/compensation) — comparing it against the matching previous-law provision when that text is
  supplied — BEFORE any peripheral or administrative change (insurance, nomination, registration).
- "old"/"old_cite" come ONLY from the PREVIOUS-law text; "new"/"new_cite" ONLY from the
  CURRENT-law text. Never swap them.
- The PREVIOUS-law text supplied is the repealed Act AS IT STOOD IMMEDIATELY BEFORE the Codes
  replaced it — later amendments are already incorporated into it. Take every "old" figure from
  that text as printed. NEVER reconstruct an earlier version of the Act from amendment history
  or from memory (e.g. if the supplied Maternity Benefit Act text says twenty-six weeks, the
  old position IS twenty-six weeks — a change made by an earlier amendment is NOT a change made
  by the Codes, and reporting it as one overstates what changed).
- Base every "old" on the supplied PREVIOUS-LAW text. If that text does not cover a point, do NOT
  assert the requirement is new or that "no equivalent existed" — the predecessor may simply not be
  among the supplied excerpts (e.g. provident fund, ESI and gratuity all existed under earlier Acts).
  Instead set "old" to "Previous-law text not available to compare" and "old_cite" to "".
- If NO previous-law text is supplied for the topic at all, return a SINGLE change with that "old",
  the current requirement in "new"/"new_cite", a neutral "headline" ("Comparison limited — previous-
  law text for this topic wasn't found"), and an "impact" describing the current obligation. Do NOT
  claim the topic is newly introduced, and never return an empty "changes" list.
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
    """Turn raw AWS errors into clear, actionable guidance for the operator — always surfacing the
    real reason (the underlying message is appended) so account-gating is never masked."""
    msg = str(e)
    low = msg.lower()
    tail = f"\n\n_Details: {msg[:200]}_"
    if "use case" in low and ("submit" in low or "not been submitted" in low):
        return (
            "\n\n⚠️ **This model needs a one-time use-case submission on your AWS account.**\n"
            "In **AWS Console → Bedrock → Model access**, enable the model and submit the provider's "
            "use-case details form (Anthropic Claude and some others require this), then retry." + tail
        )
    if ("payment" in low or "marketplace subscription" in low
            or "invalid_payment_instrument" in low):
        return (
            "\n\n⚠️ **This model needs an active AWS Marketplace subscription / valid billing.**\n"
            "In **AWS Console → Bedrock → Model access**, subscribe to the model (Cohere and other "
            "third-party models are sold via Marketplace and need a valid payment instrument), wait "
            "~2 minutes, and retry. First-party models (Amazon Titan, Mistral) need no subscription." + tail
        )
    if ("model identifier is invalid" in low or "resourcenotfound" in low
            or "is not supported" in low or "isn't supported" in low
            or "don't have access to the model" in low
            or "do not have access to the model" in low):
        return (
            "\n\n⚠️ **The configured model isn't available to this account/region.**\n"
            "Check **`BEDROCK_MODEL_ID`** and set **`AWS_REGION`** to a region that serves it "
            "(e.g. `us-east-1`), and enable it under **Bedrock → Model access**." + tail
        )
    if ("accessdenied" in low or "not authorized" in low
            or "could not be validated" in low):
        return (
            "\n\n⚠️ **AWS denied access.** Confirm `AWS_BEARER_TOKEN_BEDROCK` is valid with the "
            "`bedrock:InvokeModel` permission, and that the model is enabled in your region." + tail
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
                   max_tokens: int = 8192, temperature: float = 0.0,
                   on_progress=None) -> dict:
    """Single Converse call returning parsed JSON (or a raw-text fallback).
    Headroom (8192 tokens) lets the model reason through several issues without truncation.
    Temperature 0.0: this is a legal tool — the same question should give the same answer; a
    warmer setting (was 0.25) made verdicts and citations drift between identical runs.

    With `on_progress`, the call STREAMS (converse_stream) and invokes on_progress(n_words)
    as tokens arrive — the answer is still parsed whole at the end (the JSON contract is
    untouched), but the UI can show live drafting progress instead of a frozen spinner.
    Any streaming failure falls back to one blocking call, so streaming can never make an
    answer worse — only the progress display degrades."""
    client = get_bedrock_client()
    if not client:
        return {"_raw": "⚠️ Bedrock client error. Check secrets."}
    if not _has_key():
        return {"_raw": "⚠️ Add **AWS_BEARER_TOKEN_BEDROCK** and **AWS_REGION** in "
                        "*App → Settings → Secrets*."}
    kwargs = dict(
        modelId=_model_id(),
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    text, stop_reason = None, None
    if on_progress is not None:
        try:
            stream = client.converse_stream(**kwargs)
            parts, n_since = [], 0
            for ev in stream["stream"]:
                if "contentBlockDelta" in ev:
                    parts.append(ev["contentBlockDelta"]["delta"].get("text", ""))
                    n_since += 1
                    if n_since >= 8:             # throttle UI updates (~every 8 chunks)
                        n_since = 0
                        try:
                            on_progress(sum(p.count(" ") for p in parts))
                        except Exception:
                            pass
                elif "messageStop" in ev:
                    stop_reason = ev["messageStop"].get("stopReason")
            text = "".join(parts)
        except Exception:
            text = None                          # fall through to one blocking retry
    if text is None:
        try:
            resp = client.converse(**kwargs)
            stop_reason = resp.get("stopReason")
            content = resp.get("output", {}).get("message", {}).get("content", [])
            text = next((b["text"] for b in content if isinstance(b, dict) and "text" in b), "")
        except Exception as e:
            return {"_raw": _friendly_bedrock_error(e)}
    if stop_reason == "max_tokens":
        # The JSON answer was cut off mid-stream; parsing it would dump broken JSON at the
        # user. Tell them to narrow the question instead.
        return {"_raw": "⚠️ The answer was cut off before it finished (length limit). "
                        "Please narrow the question or ask about one issue at a time."}
    return _parse_answer(text)


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


def generate_answer(messages: list[dict], on_progress=None) -> dict:
    """Structured single answer (verdict / info)."""
    return _reconcile_verdict(
        _converse_json(SYSTEM, messages[-1]["content"], on_progress=on_progress))


def generate_comparison(user_text: str, on_progress=None) -> dict:
    """Old-Act vs new-Code 'what changed' comparison."""
    return _converse_json(COMPARISON_SYSTEM, user_text, on_progress=on_progress)


QUERY_REWRITE_SYSTEM = """You turn an HR manager's question or situation into a compact set of SEARCH
KEYWORDS for looking up Indian labour-law provisions. Expand plain-English wording into the statute's
own terms and close synonyms — e.g. "fire / let go / sack" -> "termination dismissal retrenchment
discharge", "time off for a baby" -> "maternity benefit leave", "PF" -> "provident fund".
Output ONLY keywords and short phrases, space-separated, lowercase, no punctuation, no explanation."""

_query_terms_cache: dict = {}
_QUERY_TERMS_CACHE_MAX = 512   # bound so a long-running server doesn't leak one entry per query

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
            if len(_query_terms_cache) >= _QUERY_TERMS_CACHE_MAX:
                _query_terms_cache.clear()
            _query_terms_cache[q] = out
        return out
    except Exception:
        return ""


_COMPARE_RE = re.compile(
    r"\b(what (?:has |have )?chang(?:ed|es)|has chang(?:ed|es)|chang(?:ed|es) (?:from|since|in)|"
    r"old acts?|old laws?|earlier laws?|previously|before the codes?|used to|compared to|"
    r"comparison|difference|differ|new vs old|old vs new|replaced|repeal)\b", re.I)

def _is_comparison(query: str) -> bool:
    return bool(_COMPARE_RE.search(query))


# Words that carry NO topic in a comparison question — the question's own meta-language
# ("what changed", "old laws", "new codes") plus generic filler. A comparison query whose
# every token is in this set has nothing for retrieval to bite on: grounding it on the raw
# query surfaces a grab-bag of unrelated Sections, and the model — correctly forbidden from
# manufacturing differences — returns an empty comparison. Those queries take the curated
# overview path instead (build_overview_comparison_prompt).
_CMP_META_WORDS = frozenset("""
a an the and or of in on for to from with under at by so that this these those there
what which how why when where is are was were be been being s do does did done has have had
can could will would should shall may might must
i we me us my our you your they them it its he she his her
change changes changed changing new old newer older earlier previous previously prior latest
current recent now today recently
law laws act acts code codes rule rules regulation regulations provision provisions
amendment amendments reform reforms regime system framework
labour labor india indian government central
compare compared comparing comparison contrast difference differences differ different
between versus vs against
tell explain give show list summarise summarize summary overview brief detail details
know understand happened please about regarding exactly really actually
major key main big biggest important significant notable everything anything all any some
employee employees worker workers workman workmen staff people
employer employers company companies establishment establishments business firm hr manager managers
repeal repealed replace replaced replacing subsumed since before after
one ones four 4 2019 2020 year years
""".split())


def _is_generic_comparison(query: str) -> bool:
    """True for a comparison question with no substantive topic ("what changed from the old
    laws?") — every token is comparison meta-language or filler. Topical comparison questions
    ("how has gratuity changed…") keep the normal retrieval-grounded path."""
    toks = re.findall(r"[a-z0-9]+", query.lower())
    return bool(toks) and all(t in _CMP_META_WORDS for t in toks)


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

# ── Deterministic amount calculators ─────────────────────────────────────────
# LLMs compute statutory amounts unreliably (they drop the ÷26 factor, vary run to run),
# so where the Code fixes a clean formula we compute the figure in code from a parsed
# tenure + monthly wage and hand the model the result to STATE, not recompute.
_WAGE_RE = (r"(?:rs\.?|inr|₹)?\s*(\d{3,})\s*(?:/?\s*(?:per\s+)?month|/month|monthly|a month|p\.?m\b)",
            r"(?:drawing|earning|salary(?:\s+of)?|wages?\s+of|last\s+drawn(?:\s+wages?)?(?:\s+of)?)"
            r"\s*(?:rs\.?|inr|₹)?\s*(\d{3,})")

def _parse_tenure_wage(ql: str):
    """From a comma-stripped lowercased query, pull (completed_years, extra_months,
    monthly_wage). Returns None unless BOTH a year count and a monthly wage are present."""
    ym = re.search(r"(\d{1,2})\s*(?:completed\s+)?(?:years?|yrs?)\b", ql)
    if not ym:
        return None
    years = int(ym.group(1))
    mm = re.search(r"(\d{1,2})\s*months?\b", ql)
    months = int(mm.group(1)) if mm else 0
    wm = re.search(_WAGE_RE[0], ql) or re.search(_WAGE_RE[1], ql)
    if not wm:
        return None
    wage = int(wm.group(1))
    if wage < 1000 or not (1 <= years <= 60):
        return None
    return years, months, wage


# Gratuity is capped at the ceiling notified by the Central Government under §53(4)(b) of
# the Code on Social Security, 2020 — currently ₹20,00,000. Without this cap the app states
# a figure ABOVE the statutory maximum to HR as law for high-wage / long-tenure cases.
GRATUITY_CEILING = 2_000_000

def gratuity_estimate(query: str):
    """Gratuity for a monthly-rated employee — Code on Social Security §53(2): (monthly
    wages ÷ 26) × 15 per completed year, a part-year over six months counting as a year,
    capped at the §53(4)(b) ceiling. None unless it is a gratuity question with a clean
    tenure + monthly wage."""
    ql = query.lower().replace(",", "")
    if "gratuit" not in ql:
        return None
    tw = _parse_tenure_wage(ql)
    if not tw:
        return None
    years, months, wage = tw
    eff = years + (1 if months > 6 else 0)
    raw = round(wage / 26 * 15 * eff)
    amount = min(raw, GRATUITY_CEILING)
    return {"years": years, "months": months, "eff": eff, "wage": wage,
            "amount": amount, "raw": raw, "capped": raw > GRATUITY_CEILING}


def _amount_notes(query: str) -> list:
    """Calculation notes to bind into the prompt — each a (heading, body) pair. Covers the
    amounts the Code fixes cleanly enough to compute; lay-off (needs days) and overtime
    (needs hours) are left as formulae since their day/hour inputs and divisors are not
    pinned by the Code."""
    notes = []
    ql = query.lower().replace(",", "")

    g = gratuity_estimate(query)
    if g:
        yrs = f"{g['years']} years" + (f" {g['months']} months" if g['months'] else "")
        if g["capped"]:
            tail = (f"₹{g['raw']:,}, which exceeds the ₹20,00,000 ceiling notified under "
                    f"§53(4)(b); gratuity is therefore capped at ₹{g['amount']:,}.")
        else:
            tail = (f"₹{g['amount']:,} (within the ₹20,00,000 ceiling notified under §53(4)(b)).")
        notes.append(("GRATUITY",
            f"Per §53(2) of the Code on Social Security, for a monthly-rated employee gratuity = "
            f"(monthly wages ÷ 26) × 15 for each completed year, a part-year over six months "
            f"counting as a full year. For ₹{g['wage']:,}/month and {yrs} (= {g['eff']} years): "
            f"₹{g['wage']:,} ÷ 26 × 15 × {g['eff']} = {tail}"))

    # Retrenchment dues — §70: one month's notice (or wages in lieu) AND compensation of
    # 15 days' average pay per completed year (part over six months = a year). The Code does
    # not fix the day-divisor for "average pay", so we use the 26-day method (as §53 does for
    # gratuity) and show the working, rather than asserting it as the only reading.
    if "retrench" in ql:
        tw = _parse_tenure_wage(ql)
        if tw:
            years, months, wage = tw
            eff = years + (1 if months > 6 else 0)
            comp = round(wage / 26 * 15 * eff)
            yrs = f"{years} years" + (f" {months} months" if months else "")
            notes.append(("RETRENCHMENT DUES",
                f"Per §70 of the Industrial Relations Code, a worker in continuous service for "
                f"at least a year gets: (a) one month's notice OR ₹{wage:,} wages in lieu of "
                f"notice; and (b) compensation of 15 days' average pay for each completed year "
                f"(part over six months = a year). Using the 26-day method for average pay: "
                f"₹{wage:,} ÷ 26 × 15 × {eff} = ₹{comp:,} for {yrs}. If notice is paid in lieu, "
                f"total cash ≈ ₹{wage + comp:,}. (Average-pay divisor not fixed by the Code; "
                f"shown on the 26-day basis.)"))

    # Lay-off compensation — §67: 50% of (basic wages + DA) for each day laid off. Fires only
    # on an explicit "laid off for N days" + a monthly wage. The day-divisor and the basic+DA
    # split aren't fixed by the Code, so we use total monthly wage on the 26-day basis and say so.
    wm = re.search(_WAGE_RE[0], ql) or re.search(_WAGE_RE[1], ql)
    if wm and re.search(r"lay[\s-]?off|laid[\s-]?off", ql):
        dm = (re.search(r"la(?:y|id)[\s-]?off\b.{0,40}?(\d{1,3})\s*days?", ql)
              or re.search(r"(\d{1,3})\s*days?.{0,40}?la(?:y|id)[\s-]?off", ql))
        if dm:
            days = int(dm.group(1)); wage = int(wm.group(1))
            if 1 <= days <= 365 and wage >= 1000:
                comp = round(0.5 * (wage / 26) * days)
                notes.append(("LAY-OFF COMPENSATION",
                    f"Per §67 of the Industrial Relations Code, a laid-off worker is paid 50% of "
                    f"(basic wages + dearness allowance) for each day of lay-off (bar weekly "
                    f"holidays). Taking ₹{wage:,}/month as the wage base on the 26-day method: "
                    f"50% × (₹{wage:,} ÷ 26) × {days} days = ₹{comp:,}. (Treats monthly wage as "
                    f"basic+DA on the 26-day basis; neither is fixed by the Code.)"))

    # Overtime — Code on Wages §14 / OSH §27: twice the normal rate. Fires only on explicit
    # "N hours of overtime" + a monthly wage (NOT "worked N hours a day"). Normal hourly rate
    # taken as monthly ÷ (26 days × 8 hours) — a stated convention, not fixed by the Code.
    if wm and re.search(r"over[\s-]?time", ql):
        hm = (re.search(r"(\d{1,3})\s*(?:hours?|hrs?)\s*(?:of\s+)?(?:over[\s-]?time)", ql)
              or re.search(r"over[\s-]?time\s*(?:of\s+|work\s+of\s+)?(\d{1,3})\s*(?:hours?|hrs?)", ql))
        if hm:
            hours = int(hm.group(1)); wage = int(wm.group(1))
            if 1 <= hours <= 300 and wage >= 1000:
                ot = round(2 * (wage / (26 * 8)) * hours)
                notes.append(("OVERTIME PAY",
                    f"Per §14 of the Code on Wages (and §27 OSH), overtime is paid at twice the "
                    f"normal rate of wages. Taking the normal hourly rate as monthly ÷ (26 days × "
                    f"8 hours): 2 × (₹{wage:,} ÷ 208) × {hours} hours = ₹{ot:,}. (The 26×8 hourly "
                    f"basis is a convention, not fixed by the Code.)"))

    # Deduction cap — §18(3): total deductions in a wage period must not exceed 50% of wages.
    # §18 IS retrieved, but the model tends to say "exceeds the limit" without the figure, so
    # state the 50% cap. Fires on a deduction-from-wages question that gives a percentage or
    # asks about the limit/maximum (not on "how much PF is deducted", which has neither).
    if (re.search(r"deduct", ql) and re.search(r"wage|salary|\bpay\b", ql)
            and (re.search(r"\d{1,3}\s*(?:%|per ?cent)", ql)
                 or re.search(r"limit|maximum|\bcap\b|exceed", ql))):
        notes.append(("DEDUCTION LIMIT",
            "Per §18(3) of the Code on Wages, the total of all deductions from an employee's "
            "wages in any wage period must not exceed 50% of those wages (any excess is "
            "recovered in the prescribed manner). State this 50% limit explicitly."))

    # Annual bonus — Code on Wages §26(1): minimum bonus is 8⅓% (= 1/12) of the wages
    # earned in the accounting year or ₹100, whichever is higher, for an employee with at
    # least 30 days' work that year; §26(3)/(5): the maximum (surplus-linked) bonus is 20%.
    # Fires on a bonus question with a monthly wage; the annualisation (12 × monthly) is a
    # stated convention. NOT fixed by the Code: the per-mensem eligibility wage ceiling and
    # the §26(2) calculation ceiling — both set by notification — so the note discloses them.
    if wm and re.search(r"\bbonus(?:es)?\b", ql) and not re.search(r"joining|sign[\s-]?on|referral", ql):
        wage = int(wm.group(1))
        if wage >= 1000:
            annual = 12 * wage
            mn = max(round(annual / 12), 100)
            mx = round(annual * 0.20)
            notes.append(("ANNUAL BONUS RANGE",
                f"Per §26(1) of the Code on Wages, an employee who has worked at least 30 days "
                f"in the accounting year is due a minimum annual bonus of 8⅓% of the wages "
                f"earned that year or ₹100, whichever is higher; per §26(3)/(5) the maximum "
                f"(where allocable surplus permits) is 20%. Taking a full year at "
                f"₹{wage:,}/month (wages earned = ₹{annual:,}): minimum = 8⅓% × ₹{annual:,} "
                f"= ₹{mn:,} (one month's wage); maximum = 20% = ₹{mx:,}. Per §39(1) the bonus "
                f"must be credited to the employee's bank account within 8 months of the close "
                f"of the accounting year. (Caveats to state: the wage ceiling for WHO qualifies "
                f"and the §26(2) ceiling on the wage USED in the calculation are both set by "
                f"government notification, not fixed in the Code — the figures above assume the "
                f"stated wage is used uncapped.)"))

    # Annual leave with wages — OSH Code §32(1)(i)-(ii): a worker who has worked 180 days
    # or more in the calendar year earns one day of leave for every 20 days worked (one per
    # 15 for adolescents and below-ground mine workers — disclosed, not computed). The
    # 180-day gate and the ÷20 accrual are both fixed in the Code, so both branches are
    # deterministic. Fires only on a leave question with an explicit "worked N days".
    if re.search(r"\bleave\b", ql) and not re.search(r"maternity|pregnan", ql):
        lm = re.search(r"work(?:ed|s|ing)?\s*(?:for\s*)?(\d{1,3})\s*days?", ql)
        if lm:
            days = int(lm.group(1))
            if 1 <= days <= 366:
                if days >= 180:
                    notes.append(("ANNUAL LEAVE ENTITLEMENT",
                        f"Per §32(1) of the OSH Code, a worker who has worked 180 days or more "
                        f"in the calendar year is entitled to one day of leave with wages for "
                        f"every 20 days worked. For {days} days worked: {days} ÷ 20 = "
                        f"{days // 20} days of leave. (Adolescent workers and workers below "
                        f"ground in a mine accrue at one day per 15 days worked instead. Unused "
                        f"leave carries forward up to 30 days — §32(1)(vii); leave refused "
                        f"carries forward without limit.)"))
                else:
                    notes.append(("ANNUAL LEAVE ENTITLEMENT",
                        f"Per §32(1)(i) of the OSH Code, the annual-leave entitlement (one day "
                        f"per 20 days worked) requires 180 days or more worked in the calendar "
                        f"year; {days} days does NOT cross that threshold. (Exception to state: "
                        f"a worker whose service began mid-year qualifies by working one-fourth "
                        f"of the remaining days — §32(1)(v); lay-off, maternity leave and "
                        f"earlier annual leave count toward the 180 days — §32(1)(iii).)"))

    # Final-settlement deadline — Code on Wages §17(2): wages must be paid within TWO
    # WORKING DAYS of removal, dismissal, retrenchment or resignation (incl. closure).
    # Statement-only note (like DEDUCTION LIMIT): fires on a termination-event question
    # with a timing cue, so it never fires on bare "when must wages be paid?".
    if (re.search(r"remov|dismiss|retrench|resign|terminat|sack|fired?\b|closure|closing down", ql)
            and re.search(r"full\s*(?:and|&)\s*final|final settlement|settle|"
                          r"when\b.{0,60}\b(?:pay|paid|wages|dues)|"
                          r"(?:pay|paid|wages|dues)\b.{0,60}\bwhen|within how|how (?:soon|long)|"
                          r"time[\s-]?limit|deadline", ql)):
        notes.append(("FINAL WAGES DEADLINE",
            "Per §17(2) of the Code on Wages, where an employee is removed, dismissed, "
            "retrenched, resigns, or becomes unemployed due to closure, the wages payable "
            "must be paid within TWO WORKING DAYS of that event. State this deadline "
            "explicitly. (§17(3): the appropriate Government may notify a different time "
            "limit; ordinary monthly wages are otherwise due before the 7th of the "
            "following month — §17(1).)"))

    # Gratuity payment deadline — SS Code §56(3): within 30 days of becoming payable,
    # failing which simple interest runs (§56(4), rate notified — not fixed by the Code).
    # Statement-only; fires on a gratuity question with a timing/late cue.
    if "gratuit" in ql and re.search(r"\blate\b|delay|not (?:been )?paid|unpaid|when\b|within|"
                                     r"how (?:soon|long)|time[\s-]?limit|deadline|interest", ql):
        notes.append(("GRATUITY PAYMENT DEADLINE",
            "Per §56(3) of the Code on Social Security, the employer must arrange to pay "
            "gratuity within THIRTY DAYS from the date it becomes payable; per §56(4), if "
            "unpaid in that period, simple interest runs from the due date to payment (at "
            "a rate notified by the Central Government — the rate itself is not fixed in "
            "the Code)."))

    # Maternity-benefit branch selection — SS Code §60(3)-(4). The DEFAULT 26-week period
    # is retrieved reliably; what the model misses are the provisos, so this fires only
    # when a proviso fact is stated: two or more surviving children -> 12 weeks (max 6
    # pre-delivery); adoption (child under 3 months) / commissioning mother -> 12 weeks
    # from handover. Also the §60(2) 80-day eligibility gate when "worked N days" is given.
    if re.search(r"maternity|pregnan|childbirth|adopt|commissioning", ql):
        if re.search(r"(?:two|2|three|3|four|4)\s*(?:or more\s*)?(?:surviving\s*)?"
                     r"(?:children|kids)|second child|third child", ql):
            notes.append(("MATERNITY BENEFIT PERIOD",
                "Per the first proviso to §60(3) of the Code on Social Security, a woman who "
                "already has TWO OR MORE SURVIVING CHILDREN is entitled to a maximum of "
                "TWELVE weeks of maternity benefit (not 26), of which not more than six weeks "
                "may precede the expected delivery date. State 12 weeks, not the general 26."))
        elif re.search(r"adopt|commissioning", ql):
            notes.append(("MATERNITY BENEFIT PERIOD",
                "Per §60(4) of the Code on Social Security, a woman who legally adopts a child "
                "below the age of three months, or a commissioning mother, is entitled to "
                "TWELVE weeks of maternity benefit from the date the child is handed over. "
                "(A child adopted at three months or older is outside §60(4)'s words — "
                "disclose that limit rather than assuming 12 weeks applies.)"))
        wd = re.search(r"work(?:ed|s|ing)?\s*(?:for\s*|only\s*)?(\d{1,3})\s*days?", ql)
        if wd and re.search(r"maternity|pregnan", ql):
            days = int(wd.group(1))
            if 1 <= days <= 366:
                verdict = ("crosses" if days >= 80 else "does NOT cross")
                notes.append(("MATERNITY ELIGIBILITY (80 DAYS)",
                    f"Per §60(2) of the Code on Social Security, maternity benefit requires "
                    f"having actually worked at least EIGHTY days in the twelve months "
                    f"immediately preceding the expected delivery date; {days} days worked "
                    f"{verdict} that threshold. (Days laid off and paid holidays count toward "
                    f"the 80 — §60(2) Explanation.)"))
    return notes


def build_prompt(query: str, all_results: dict, applicability=None) -> str:
    grounding = corpus.render_all_results(all_results, query)
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
    for heading, body in _amount_notes(query):
        # Figures computed in code from the Code — state them, don't recompute. Some (lay-off,
        # overtime) rest on a stated convention (e.g. 26-day divisor, gross-as-basic+DA); the
        # note body spells that out, so require the caveat to be carried through rather than
        # presented as a hard statutory amount.
        parts.append(f"=== {heading} (state this exact figure AND any caveat shown with it; "
                     f"do NOT recompute) ===\n{body}")
    parts.append(f"=== QUESTION ===\n{query}")
    return "\n\n".join(parts)

# Query → overview-topic pins for TOPICAL comparisons. The lexically-ranked search_old top-k
# can drop the topic's CORE provision (the Maternity Benefit Act's §5 fell to rank 7 and the
# model was left comparing against notice/records sections), so when the query names one of
# the curated topics, its flagship old/new provisions are pinned into the grounding.
_CMP_TOPIC_PINS = [
    (re.compile(r"retrench|lay[\s-]?off|clos(?:e|ing|ure)|shut", re.I), 0),
    (re.compile(r"strike|lock[\s-]?out", re.I), 1),
    (re.compile(r"minimum wage|floor wage|\bwages?\b|salary", re.I), 2),
    (re.compile(r"\bbonus", re.I), 3),
    (re.compile(r"gratuity", re.I), 4),
    (re.compile(r"maternity|pregnan|childbirth", re.I), 5),
    (re.compile(r"working hours|overtime|\bleave\b|holiday", re.I), 6),
]


def _pinned_cmp_chunks(query: str) -> tuple[list, list]:
    """(new_chunks, old_chunks) pinned for the overview topics the query names. Marked _pin so
    they render UNTRIMMED — the core clause being compared must never fall to the trim cap."""
    pin_new, pin_old = [], []
    for pat, ti in _CMP_TOPIC_PINS:
        if not pat.search(query):
            continue
        label, cid, new_lbls, old_map = _OVERVIEW_TOPICS[ti]
        entry = LOADED.get(cid)
        if not entry:
            continue
        pin_new += [{**c, "_pin": True} for c in _pick_chunks(entry["chunks"], new_lbls)]
        for oa in entry.get("old_acts", []):
            want = old_map.get(oa["meta"]["slug"])
            if want:
                pin_old += [{**c, "_pin": True} for c in _pick_chunks(oa["chunks"], want)]
    return pin_new, pin_old


def build_comparison_prompt(query: str, all_results: dict) -> str:
    pin_new, pin_old = _pinned_cmp_chunks(query)
    # Pins always win: the ranked copy of a pinned provision is dropped so the untrimmed pinned
    # copy is the one the model reads (the ranked copy is trim-capped and can lose the clause).
    pinned_keys = {(c["source"], c["label"]) for c in pin_new}
    ranked = {cid: ({**r, "chunks": [c for c in r["chunks"]
                                     if (c["source"], c["label"]) not in pinned_keys]}
                    if r["found"] else r)
              for cid, r in all_results.items()}
    for r in ranked.values():
        r["found"] = bool(r["chunks"])
    new_g = corpus.render_all_results(ranked, query)
    if pin_new:
        new_g += "\n\n" + corpus.render_chunks(pin_new, query)
    olds = list(pin_old)
    seen_old = {(c["source"], c["label"]) for c in pin_old}
    for cid, r in all_results.items():
        if not r["found"]:
            continue
        for c in corpus.search_old(LOADED[cid], query, k=6):
            key = (c["source"], c["label"])
            if key not in seen_old:
                seen_old.add(key)
                olds.append(c)
    old_g = (corpus.render_chunks(olds, query) if olds
             else "(No repealed-Act text found for this topic.)")
    return (f"=== CURRENT LAW (in force) ===\n{new_g}\n\n"
            f"=== PREVIOUS LAW (repealed Acts) ===\n{old_g}\n\n"
            f"=== QUESTION ===\n{query}")


# The headline old→new changes, pinned to their flagship provisions so a broad "what changed?"
# question is grounded on ALIGNED old/new pairs rather than whatever chunks happen to contain
# the words "old"/"law"/"changed". Each entry: (topic label, code id, new-Code provision
# labels, {old-Act slug: provision labels}). Every pinned label is verified by
# tests/test_comparison.py, so a corpus change can't silently empty a topic.
_OVERVIEW_TOPICS = [
    ("Retrenchment & closure — Government-permission threshold, notice and compensation", "ir",
     ["Section 70", "Section 77"],
     {"industrial_disputes": ["Section 25F", "Section 25K", "Section 25N"]}),
    ("Strikes & lock-outs — notice requirements", "ir",
     ["Section 62"],
     {"industrial_disputes": ["Section 22", "Section 23"]}),
    ("Minimum wages & the new floor wage", "wages",
     ["Section 5", "Section 6", "Section 9"],
     {"minimum_wages": ["Section 3", "Section 5"]}),
    ("Annual bonus — eligibility and minimum", "wages",
     ["Section 26"],
     {"payment_of_bonus": ["Section 8", "Section 10"]}),
    ("Gratuity", "ss",
     ["Section 53"],
     {"payment_of_gratuity": ["Section 4"]}),
    ("Maternity benefit", "ss",
     ["Section 60"],
     {"maternity_benefit": ["Section 5"]}),
    ("Working hours, overtime & annual leave", "osh",
     ["Section 25", "Section 27", "Section 32"],
     {"factories": ["Section 54", "Section 59", "Section 79"]}),
]


def _pick_chunks(chunks: list, labels: list) -> list:
    by = {c["label"]: c for c in chunks}
    return [by[l] for l in labels if l in by]


def build_overview_comparison_prompt(query: str) -> tuple[str, list[str]]:
    """Grounding for a BROAD comparison question ("what changed from the old laws?"), organised
    as per-topic old/new pairs from _OVERVIEW_TOPICS. Returns (prompt, source shorts)."""
    parts, shorts = [], []
    for label, cid, new_lbls, old_map in _OVERVIEW_TOPICS:
        entry = LOADED.get(cid)
        if not entry:
            continue
        new_c = [{**c, "_pin": True} for c in _pick_chunks(entry["chunks"], new_lbls)]
        old_c = []
        for oa in entry.get("old_acts", []):
            want = old_map.get(oa["meta"]["slug"])
            if want:
                old_c += [{**c, "_pin": True} for c in _pick_chunks(oa["chunks"], want)]
        # Fail-soft if a pinned provision vanishes from the corpus: fall back to topical search
        # so the block degrades to "best effort" instead of disappearing.
        if not new_c:
            new_c = corpus.search(entry, label, k=2)
        if not old_c:
            old_c = corpus.search_old(entry, label, k=2)
        if not new_c or not old_c:
            continue                      # an overview topic is only useful with BOTH sides
        short = entry["meta"]["short"]
        if short not in shorts:
            shorts.append(short)
        parts.append(f"### TOPIC: {label}\n"
                     f"--- CURRENT LAW (in force) ---\n{corpus.render_chunks(new_c, label)}\n"
                     f"--- PREVIOUS LAW (repealed Act) ---\n{corpus.render_chunks(old_c, label)}")
    head = ("The manager asked a BROAD question about what changed overall under the new Labour "
            "Codes. The grounding below is organised by TOPIC; each topic pairs the CURRENT "
            "Code text with the matching PREVIOUS (repealed-Act) text. Give one \"changes\" "
            "entry per topic whose texts actually differ, in the order the topics appear; skip "
            "a topic only if its two texts say the same thing.")
    return (head + "\n\n" + "\n\n".join(parts) + f"\n\n=== QUESTION ===\n{query}", shorts)

def _correction_html(corrections):
    # `o` is the raw user token (from q.split()) — escape both sides before they enter this
    # unsafe_allow_html block, or a crafted question injects HTML into the rendered page.
    pairs = ", ".join(
        f'<strong>{_esc(o)}</strong> → <strong>{_esc(f)}</strong>' for o, f in corrections
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
    # Statute text carries PDF line-wrap newlines (~one every 76 chars, mid-sentence). A hard <br>
    # per line breaks sentences and renders ragged/"vertical" in narrow containers, so reflow:
    # split on blank-line paragraph breaks, collapse each paragraph's wrapped lines to spaces,
    # and rejoin paragraphs with a single <br> (the browser then wraps to the available width).
    paras = re.split(r"\n[ \t]*\n+", _esc(x))
    paras = [re.sub(r"\s*\n\s*", " ", para).strip() for para in paras]
    return "<br>".join(para for para in paras if para)

def _clean_citation(c: str) -> str:
    """Tidy a citation for the answer sub-line: drop the [ ] some Code names carry."""
    return str(c or "").replace("[", "").replace("]", "").strip()

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
    with st.expander(label, expanded=False):
        for a in auths:
            v = a.get("verified")
            badge = ('<span class="lc-verified">✓ verbatim</span>' if v
                     else '<span class="lc-unverified">⚠ unverified</span>' if v is False else '')
            cls = " unverified" if v is False else ""
            # Show the FULL provision in the opt-in panel — it's drill-down, so never truncate
            # it to "[...]"; the user opened it precisely to read the complete section.
            text = (a.get("source_text") or a.get("quote", "")).strip()
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
    changes = [c for c in (data.get("changes") or []) if isinstance(c, dict)]
    if hl:
        st.markdown(f'<div class="lc-cmp-headline">🔄 {_esc(hl)}</div>', unsafe_allow_html=True)
    # No point-by-point changes — usually because the previous-law text for this topic wasn't
    # found among the repealed Acts in the corpus. Say that honestly; do NOT assert the
    # requirement is new (the predecessor may simply be missing, e.g. PF/ESI/gratuity).
    if not changes:
        msg = hl or ("A point-by-point comparison isn't available — the previous-law text for this "
                     "topic wasn't found in the repealed Acts. The current statutory text is shown below.")
        st.markdown(f'<div class="lc-cmp-empty">ℹ️ {_esc(msg)}</div>', unsafe_allow_html=True)
    for ch in changes:
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
    if isinstance(data, dict) and "_raw" not in data and (
            data.get("type") == "comparison"
            or (isinstance(data.get("changes"), list) and data.get("changes"))):
        # Also route comparison-shaped answers whose "type" key the model dropped —
        # they'd otherwise fall through every info/compliance section and render blank.
        render_comparison(data)
        return
    if not isinstance(data, dict) or "_raw" in data:
        st.markdown(data.get("_raw", "") if isinstance(data, dict) else str(data))
        st.markdown(f'<div class="lc-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)
        return

    # Safety net: valid JSON matching NEITHER answer schema (no known text, list, or verdict
    # key) must never render as an empty card — show whatever prose the model returned.
    _text_keys = ("direct_answer", "restatement", "answer", "headline")
    _list_keys = ("analysis", "key_points", "requirements", "actions", "authorities")
    _verd = data.get("verdict")
    if (not any(str(data.get(k) or "").strip() for k in _text_keys)
            and not any(isinstance(data.get(k), list) and data.get(k) for k in _list_keys)
            and not (isinstance(_verd, dict)
                     and str(_verd.get("summary") or _verd.get("status") or "").strip())):
        prose = [str(v).strip() for v in data.values()
                 if isinstance(v, str) and str(v).strip()]
        if prose:
            st.markdown("\n\n".join(_esc(p) for p in prose))
        else:
            st.markdown("⚠️ The answer came back in an unexpected format — please try "
                        "rephrasing the question.")
        st.markdown(f'<div class="lc-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)
        return

    is_comp = data.get("type") == "compliance"
    verdict = data.get("verdict") or {}
    analysis = [a for a in (data.get("analysis") or []) if isinstance(a, dict)
                and (str(a.get("issue", "")).strip() or str(a.get("finding", "")).strip())]

    # 0 — Direct answer FIRST (info questions): a plain-English one-liner with the governing
    # section right under it, so a basic question gets its answer up top, before the legalese.
    direct = str(data.get("direct_answer", "")).strip()
    if not is_comp and direct:
        lead_cite = next((str(a.get("citation", "")).strip()
                          for a in analysis if str(a.get("citation", "")).strip()), "")
        cite_html = (f'<div class="lc-answer-cite">{_esc(_clean_citation(lead_cite))}</div>'
                     if lead_cite else "")
        st.markdown(
            f'<div class="lc-answer"><div class="lc-answer-label">Answer</div>'
            f'<div class="lc-answer-text">{_esc(direct)}</div>{cite_html}</div>',
            unsafe_allow_html=True)

    # 0b — Restatement (shows the situation was understood)
    restate = str(data.get("restatement", "")).strip()
    if restate:
        st.markdown(f'<div class="lc-restate">{_esc(restate)}</div>', unsafe_allow_html=True)

    # 1 — Verdict card (compliance) or lead paragraph (info, only when there's no analysis)
    status   = (verdict.get("status") or "").strip().lower()
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

    # 2 — Analysis: the dissection (issue → governing provision → application → per-issue status).
    # For a compliance verdict the headline is the verdict card, so the issue-by-issue reasoning is
    # drill-down — collapse it. For an info lookup the findings ARE the substance — keep them open.
    if analysis:
        if is_comp:
            n = len(analysis)
            with st.expander(f"Detailed reasoning · {n} point{'s' if n != 1 else ''}", expanded=False):
                _render_analysis(analysis)
        else:
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
    ("auth_user", None),       # signed-in username, or None
    ("auth_error", ""),        # last sign-in failure message, shown on the login card
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _do_login():
    typed = str(st.session_state.get("login_user", "")).strip()
    p = st.session_state.get("login_pass", "")
    users = _auth_users()
    u = _resolve_user(typed, users)
    if u is not None and _password_ok(users[u], p):
        st.session_state.auth_user = u            # canonical key, not what was typed
        st.session_state.auth_error = ""
        st.session_state.login_pass = ""          # never keep the password in state
        usage.log(u, "login")
    else:
        st.session_state.auth_error = "Wrong username/email or password — try again."
        usage.log(typed or "(blank)", "login_failed")


def _do_logout():
    u = st.session_state.get("auth_user")
    if u:
        usage.log(u, "logout")
    # Drop the account AND the conversation — the next person at this browser
    # must not see the previous user's questions.
    for k in ("auth_user", "messages", "pending", "intake", "skip_intake",
              "force_compare", "intake_got"):
        st.session_state.pop(k, None)

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

def _render_followups(query, cross, show_compare, key_prefix, follow_ups=None):
    """Beneath an answer: the model's intelligent next-question tiles (preferred), else the
    static per-topic cross-references, plus the old-law comparison button. Rendered from both
    the live turn and the history loop, so keys are prefixed per message."""
    ups = [u.strip() for u in (follow_ups or []) if isinstance(u, str) and u.strip()][:4]
    # The buttons are wrapped in keyed containers so the stylesheet can target ONLY these
    # suggestion tiles (via Streamlit's st-key-<key> container class) without restyling every
    # button in the app.
    if ups:
        st.markdown('<div class="lc-xref-label">Continue — you might ask</div>',
                    unsafe_allow_html=True)
        with st.container(key=f"fupwrap_{key_prefix}"):
            cols = st.columns(2)
            for j, q in enumerate(ups):
                cols[j % 2].button(q, key=f"{key_prefix}_f{j}", on_click=_submit_explore, args=(q,))
    elif cross:
        st.markdown('<div class="lc-xref-label">Related provisions to check</div>',
                    unsafe_allow_html=True)
        with st.container(key=f"fupwrap_{key_prefix}"):
            cols = st.columns(2)
            for j, (label, q) in enumerate(cross):
                cols[j % 2].button(label, key=f"{key_prefix}_x{j}", on_click=_submit_explore, args=(q,))
    if show_compare:
        with st.container(key=f"fupchg_{key_prefix}"):
            st.button("🔄  What changed from the old law?", key=f"{key_prefix}_chg",
                      on_click=_submit_compare, args=(query,))


class _stage_status:
    """A chevron-free replacement for st.status: one slim pulsing progress pill in a
    placeholder, updated per pipeline stage, removed entirely when the answer lands
    (st.status is an expander, so it always renders a dropdown arrow — this doesn't).
    Drop-in for the calls we make: `with ... as s:` + s.update(label=..., state=...)."""

    def __init__(self, label: str):
        self._slot = st.empty()
        self.update(label=label)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._slot.empty()                     # the rendered answer replaces the pill
        return False

    def update(self, label: str = None, state: str = None, expanded=None):
        if state == "complete":
            self._slot.empty()
        elif label:
            self._slot.markdown(
                f'<div class="lc-stage"><span class="lc-stage-dot"></span>{_esc(label)}</div>',
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ── HERO + SEARCH SECTION ────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
badges_html = "".join(
    f'<span class="lc-badge">{e["meta"]["short"]}</span>'
    for e in LOADED.values()
)

# The full hero owns the welcome screen; once a conversation starts it collapses to a slim
# bar so the answers — not the banner — own the viewport on every rerun.
_conversation_started = bool(
    st.session_state.messages or st.session_state.pending or st.session_state.intake)

if _conversation_started:
    st.markdown(f"""
<div class="lc-hero-slim">
  <div class="lc-hero-slim-mark">⚖</div>
  <div class="lc-hero-slim-name">Labour Codes <em>Assistant</em></div>
  <div class="lc-hero-slim-badges">{badges_html}</div>
</div>
""", unsafe_allow_html=True)
else:
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

# ─────────────────────────────────────────────────────────────────────────────
# Sign-in gate — active only when a [users] table exists in secrets
# ─────────────────────────────────────────────────────────────────────────────
if _auth_users() and not st.session_state.auth_user:
    with st.container(key="login_card"):
        st.markdown(
            '<div class="lc-intake-label">Sign in</div>'
            '<div class="lc-intake-head">Enter the username or email and password you were '
            'given to use the assistant.</div>',
            unsafe_allow_html=True)
        # A FORM, not bare inputs: pressing Enter submits, and both values are committed
        # atomically before the callback runs — bare inputs needed a blur before the click,
        # so typing the password and clicking straight away could sign in with a stale value.
        with st.form("login_form", clear_on_submit=False, border=False):
            st.text_input("Username or email", key="login_user", autocomplete="username",
                          placeholder="e.g. rohit — or you@company.com")
            st.text_input("Password", key="login_pass", type="password",
                          autocomplete="current-password", placeholder="••••••••")
            if st.session_state.auth_error:      # inside the form so it stays card-width
                st.markdown(
                    f'<div class="lc-auth-fail">⚠ {_esc(st.session_state.auth_error)}</div>',
                    unsafe_allow_html=True)
            st.form_submit_button("Sign in →", type="primary", on_click=_do_login)
    st.stop()

# Account row — who is signed in, how many questions they've asked, sign-out,
# and (for admins) the usage panel.
if st.session_state.auth_user:
    _user = st.session_state.auth_user
    _c1, _c2 = st.columns([4.2, 1])
    _n_q = usage.question_count(_user)
    _c1.markdown(
        f'<div class="lc-account">👤 <strong>{_esc(_user)}</strong>'
        f'<span class="lc-account-n">{_n_q} question{"s" if _n_q != 1 else ""} asked</span></div>',
        unsafe_allow_html=True)
    with _c2:
        with st.container(key="logout_wrap"):
            st.button("Sign out", key="logout_btn", on_click=_do_logout)
    if _user in _admins():
        with st.expander("📊 Usage & activity (admin)", expanded=False):
            import pandas as _pd
            _rows = usage.stats()
            if _rows:
                st.markdown('<div class="lc-section-label">Per user</div>',
                            unsafe_allow_html=True)
                st.dataframe(_pd.DataFrame([{
                    "User": r["user"], "Questions": r["questions"], "Logins": r["logins"],
                    "Last activity": _fmt_ts(r["last_seen"]),
                } for r in _rows]), hide_index=True, use_container_width=True)
                _ev = usage.recent(50)
                st.markdown('<div class="lc-section-label">Recent activity</div>',
                            unsafe_allow_html=True)
                st.dataframe(_pd.DataFrame([{
                    "When": _fmt_ts(e["ts"]), "User": e["user"], "Event": e["event"],
                    "Question": (e["detail"][:80] + "…") if len(e["detail"]) > 80 else e["detail"],
                } for e in _ev]), hide_index=True, use_container_width=True)
                _sum_csv, _act_csv = _usage_csvs()
                _today = datetime.now(_IST).strftime("%Y%m%d")
                _d1, _d2, _ = st.columns([1.4, 1.4, 1.6])
                _d1.download_button("⬇ Summary report (CSV)", _sum_csv,
                                    file_name=f"usage-summary-{_today}.csv",
                                    mime="text/csv", key="dl_summary")
                _d2.download_button("⬇ Full activity (CSV)", _act_csv,
                                    file_name=f"usage-activity-{_today}.csv",
                                    mime="text/csv", key="dl_activity")
            else:
                st.markdown("No activity recorded yet.")


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
            "type": "info",
            "direct_answer": "Gratuity is 15 days' wages for each completed year of service, "
                             "payable once an employee has 5 years of continuous service.",
            "restatement": "You're asking how gratuity works under the 2020 Codes.",
            "analysis": [
                {"issue": "When does gratuity become payable?",
                 "finding": "Gratuity is payable on resignation, retirement, superannuation, death "
                            "or disablement, once the employee has completed five years of "
                            "continuous service (the five-year rule is waived on death/disablement).",
                 "status": "info",
                 "citation": "Section 53 — Code on Social Security, 2020"},
            ],
            "follow_ups": [
                "What is the maximum gratuity payable?",
                "How is gratuity calculated for piece-rated employees?",
                "What happens if the employer pays gratuity late?",
                "Are fixed-term employees entitled to gratuity?",
            ],
            "authorities": [
                {"citation": "Section 53 — Code on Social Security, 2020", "verified": True,
                 "quote": "Gratuity shall be payable to an employee on the termination of his "
                          "employment after he has rendered continuous service for not less than "
                          "five years."},
            ],
        },
        {
            "type": "compliance",
            "follow_ups": [
                "How much retrenchment compensation is due here?",
                "Do we need government permission to retrench?",
                "Can we pay wages in lieu of the notice?",
                "What notice must be filed with the Government?",
            ],
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
            # showcase the intelligent follow-up tiles (and legacy cross-ref chips)
            _xref = intake.cross_refs(_d["_demo_topic"]) if _d.get("_demo_topic") else []
            if _d.get("follow_ups") or _xref:
                _render_followups(None, _xref, False, f"demo_{_i}", follow_ups=_d.get("follow_ups"))
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
            _render_followups(msg.get("query"), msg.get("cross") or [], _show_cmp, f"hist_{_i}",
                              follow_ups=(_d.get("follow_ups") if isinstance(_d, dict) else None))


# ─────────────────────────────────────────────────────────────────────────────
# Intake — a couple of one-tap clarifying questions when a scenario is missing decisive facts
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.intake and not st.session_state.pending:
    _ik = st.session_state.intake
    with st.chat_message("assistant", avatar="⚖️"):
        # Keyed container so the stylesheet can turn the bare radios into selectable
        # chips and dress this block as a designed card (see .st-key-intake_card rules).
        with st.container(key="intake_card"):
            st.markdown(
                '<div class="lc-intake-label">A quick check before I answer</div>'
                '<div class="lc-intake-head">Two details make the verdict precise — '
                'or skip and I\'ll answer in general terms.</div>'
                f'<div class="lc-intake-q">“{_esc(_ik["q"])}”</div>',
                unsafe_allow_html=True)
            for _fact in _ik["needed"]:
                st.radio(_fact["q"], [o[0] for o in _fact["opts"]],
                         key=f"intake_{_fact['key']}", index=None, horizontal=True)
            _b1, _b2, _ = st.columns([1.5, 1.6, 1.9])
            _b1.button("Get my answer", type="primary", key="intake_go",
                       on_click=_finalize_intake)
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
    # Wrap in the same keyed container the follow-up tiles use, so the landing samples get the
    # identical card styling (the app shouldn't look like two designs).
    with st.container(key="fupwrap_samples"):
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
    usage.log(_current_user(), "question", raw_q)

    # Show user message
    st.session_state.messages.append({"role": "user", "content": raw_q})
    with st.chat_message("user", avatar="👤"):
        st.markdown(raw_q)

    force_compare = st.session_state.force_compare
    st.session_state.force_compare = False

    with st.chat_message("assistant", avatar="⚖️"):
        if corrections:
            st.markdown(_correction_html(corrections), unsafe_allow_html=True)

        # One slim progress pill narrating the REAL pipeline stages (instead of two opaque
        # spinners): expand → search → the actual provisions being read → draft →
        # verify. Every label is derived from work that is genuinely happening. A custom
        # placeholder (not st.status) so there's no expander chevron/dropdown — just a
        # clean pulsing line that vanishes when the answer lands.
        with _stage_status("Understanding your question…") as _stat:
            if corpus.get_config().mode == "lexical":
                # Keyword-only fallback: the LLM rewrite genuinely helps paraphrases here.
                _stat.update(label="Expanding into statutory search terms…")
                extra_terms = analyze_query(raw_q)       # legal keywords; "" if offline/error
            else:
                # Embeddings carry paraphrase matching: measured over all 32 GOLD+HARD eval
                # cases in embeddings_primary mode, the rewrite changed recall in ZERO cases
                # while costing ~2s serial (its own round trip + a second query embed).
                extra_terms = ""
            _stat.update(label="Searching the four Labour Codes…")
            # Route from the original query; the expansion only sharpens ranking and may add a
            # missed code — it can never knock the relevant code below the routing gate.
            all_results = corpus.search_all(LOADED, corrected_q, k=8, boost=extra_terms)

            sources      = [r["meta"]["short"] for r in all_results.values() if r["found"]]
            no_provision = [r["meta"]["short"] for r in all_results.values() if not r["found"]]
            # Establishment-size / service gating, computed BEFORE the answer so the verdict
            # respects the threshold that decides which Chapter applies — then reused as the
            # applicability box below.
            _topic = intake.topic(corrected_q)
            _got   = st.session_state.pop("intake_got", None)
            if _got is None:
                _got = intake.facts_from_query(corrected_q)
            _notes = intake.applicability(_topic, _got or {}) if _topic else []
            # Below 300 workers, keep Chapter X prior-permission Sections out of the grounding
            # entirely (filter a shallow copy so display/routing and the quote-verifier still
            # see the full corpus; comparison keeps them — it is about what changed).
            _excl = _excluded_ir_sections(_topic, _got or {})
            _ir   = all_results.get("ir")
            _rfp  = all_results
            if _excl and _ir and _ir.get("found"):
                _rfp = {**all_results,
                        "ir": {**_ir,
                               "chunks": [c for c in _ir["chunks"] if c.get("num") not in _excl]}}
            user_msg   = build_prompt(raw_q, _rfp, applicability=_notes)
            wants_cmp   = force_compare or _is_comparison(corrected_q)
            generic_cmp = wants_cmp and _is_generic_comparison(corrected_q)
            is_compare  = generic_cmp or (bool(sources) and wants_cmp)

            cmp_prompt = None
            if generic_cmp:
                # A broad "what changed from the old laws?" has no topical keywords, so raw
                # retrieval surfaces unrelated Sections on both sides and the model — rightly
                # forbidden from manufacturing differences — used to come back empty. Ground it
                # on the curated per-topic old/new pairs instead.
                cmp_prompt, sources = build_overview_comparison_prompt(corrected_q)
                no_provision = []

            if not sources:
                names = " · ".join(e["meta"]["short"] for e in LOADED.values())
                data  = {"_raw": (
                    f"No relevant provisions found across **{names}** for this query. "
                    "Try rephrasing or ask about a specific Section or topic."
                )}
                _stat.update(label="No matching provisions found", state="complete")
            else:
                _top = [f"{c['label']} — {(c.get('title') or '').strip()} ({r['meta']['short']})"
                        if (c.get('title') or '').strip() else f"{c['label']} ({r['meta']['short']})"
                        for r in all_results.values() if r["found"] for c in r["chunks"][:1]]
                if _top and not generic_cmp:
                    _stat.update(label=f"Reading {_top[0]}"
                                 + (f" and {len(_top) - 1} more provisions…"
                                    if len(_top) > 1 else "…"))
                if is_compare:
                    _stat.update(label="Comparing the old Acts with the new Codes…"
                                 if generic_cmp else
                                 "Comparing the old Act with the new Code…")
                    data = generate_comparison(
                        cmp_prompt if generic_cmp
                        else build_comparison_prompt(corrected_q, all_results),
                        on_progress=lambda w: _stat.update(
                            label=f"Comparing old and new law… {w:,} words drafted"))
                    if isinstance(data, dict) and "_raw" not in data:
                        # The renderer routes on this key; a model that drops it must not
                        # blank the answer.
                        data["type"] = "comparison"
                else:
                    _stat.update(label="Drafting your answer…")
                    data = generate_answer(
                        [{"role": "user", "content": user_msg}],
                        on_progress=lambda w: _stat.update(
                            label=f"Drafting your answer… {w:,} words so far"))
                _stat.update(label="Verifying quotes verbatim against the Code…")
                data = _verify_quotes(data)
                _stat.update(label="Answer ready", state="complete")

        if sources or no_provision:
            st.markdown(_src_row_html(sources, no_provision), unsafe_allow_html=True)
        # Attach the (already-computed) size applicability + related-provision chips
        cross = []
        if isinstance(data, dict) and "_raw" not in data and not is_compare and _topic:
            if _notes:
                data["_applicability"] = _notes
            cross = intake.cross_refs(_topic)

        render_answer(data)
        # Offer "compare to old law" for substantive questions, but NOT for a plain definition
        # ("what is X") — comparing a definition to repealed Acts is low value and, when the old
        # text isn't well retrieved, produced misleading "newly introduced" panels.
        _show_cmp = bool(sources and not is_compare and isinstance(data, dict) and "_raw" not in data
                         and not corpus._DEFINITIONAL_RE.search(corrected_q.lower()))
        _render_followups(corrected_q, cross, _show_cmp, f"live_{len(st.session_state.messages)}",
                          follow_ups=(data.get("follow_ups") if isinstance(data, dict) else None))

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
