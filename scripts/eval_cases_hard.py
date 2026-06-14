"""
eval_cases_hard.py — harder retrieval cases for the A/B benchmark.

The existing eval_retrieval.py GOLD/cross-ref cases are (deliberately) near-saturated — every
mode scores ~100% — so they cannot discriminate retrieval strategies. These cases are designed
to be HARD for pure keyword search: each is a plain-English PARAPHRASE that avoids the statute's
own keyword (e.g. "end-of-service lump sum" instead of "gratuity"), so a paraphrase-aware ranker
(embeddings / fusion / rerank) should recover the governing Section that lexical search misses.

Each anchor (code, section) was verified against the live corpus text (scripts that print the
section body) — not guessed. Format: (query, code, target_section_num).
"""

HARD = [
    # ── Social Security ──
    ("how much of a worker's monthly salary goes toward their retirement nest egg", "ss", 16),
    ("when a long-serving employee finally leaves, what end-of-service lump sum is due", "ss", 53),
    ("is a woman entitled to paid time off when she has a baby", "ss", 60),
    ("how should an expecting employee formally apply to receive her childbirth leave pay", "ss", 62),
    # ── Wages ──
    ("can the centre set a nationwide baseline pay level below which earnings cannot fall", "wages", 9),
    ("if staff put in more hours than their fixed daily schedule, what pay applies", "wages", 14),
    ("what yearly profit-linked payment must employers give their lower-paid staff", "wages", 26),
    # ── OSH ──
    ("in a factory, what is the wage rate for time worked beyond the normal limit", "osh", 27),
    ("how many hours a day and a week can a worker be made to work", "osh", 25),
    ("must an employer hand every new hire a formal written job document", "osh", 6),
    ("how many paid days off does a worker build up over a calendar year", "osh", 32),
    # ── Industrial Relations ──
    ("what must a company pay and do before letting workers go because of surplus staff", "ir", 70),
    ("how far in advance must employees warn before walking off the job", "ir", 62),
    ("if we permanently shut a unit, what is owed to the workers who lose their jobs", "ir", 75),
]
