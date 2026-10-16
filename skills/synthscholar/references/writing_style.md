# Writing style for the review's prose

A systematic review is read as a formal scientific document. It is also, here,
generated, and generated prose has a recognisable statistical-average voice:
inflated significance, stacked hedges, vague quantities, and phrases no author
in the field would write. This file is the style the review's own prose must
meet. `scripts/check_writing.py` flags most of these patterns mechanically;
the rest need a careful read.

Adapted from the *humanizer* pattern guide (v2.1.1, by @blader, after
Wikipedia's "Signs of AI writing", WikiProject AI Cleanup), with its formal
scientific register section, and specialised for PRISMA reviews: GRADE
certainty language, study counts, and attribution to included studies.

## What this applies to, and what it must never touch

**Restyle** only the review's own prose: abstract, introduction, methods
narrative, results narrative, synthesis and themes, discussion, conclusion,
limitations, risk-of-bias and GRADE summaries, per-group answers, and the
narrative-table cells.

**Never restyle**:

- **Quoted or extracted text.** Evidence spans, charted answers, appraisal
  items and anything a study said verbatim. Changing them breaks grounding.
- **Numbers.** Effect sizes, CIs, p values, counts, PRISMA flow figures.
- **Identifiers and citations.** PMIDs, DOIs and author–year citations
  (`verify_citations.py` re-checks them afterwards).
- **Research questions and search strings**, which are recorded inputs.
- **GRADE ratings and risk-of-bias judgements.** Rewording the sentence
  around a rating is fine; changing the rating is not.

**A rewrite may not add a claim, a number or a citation** that is not already
in the review's data. If a sentence is vague because the number is missing,
find the number in the charting or evidence. If it isn't there, make the
sentence honestly unquantified ("the included studies did not report effect
sizes"); never invent one.

## The review-specific rules (apply first)

| Rule | Instead of | Write |
| --- | --- | --- |
| **Count the studies** | "Many studies found…", "Most research suggests…" | "Seven of the 12 included studies reported…" |
| **Attribute findings** | "Research shows that X improves Y" | "Three cohort studies (Smith et al., 2021; Lee et al., 2022; Ortiz et al., 2023) reported improvement in Y" |
| **Separate study claims from the review's findings** | "X causes Y" (stated by one study) | "Smith et al. (2021) concluded that X causes Y; the other four studies did not test causation" |
| **Observational evidence is associative** | "X leads to / drives / causes Y" | "X was associated with Y" |
| **"Significant" only with a test** | "a significant improvement" | "a statistically significant improvement (p = 0.01; Lee et al., 2022)" or "a 12% improvement" |
| **GRADE wording matches the certainty** (GRADE informative statements) | "X reduces Y" at low certainty | High: "X reduces Y". Moderate: "X probably reduces Y". Low: "X may reduce Y". Very low: "The evidence is very uncertain about the effect of X on Y" |
| **Say what was not done** | (silence) | "A meta-analysis was not performed because outcome measures differed across studies." |
| **The review does not prove** | "This review demonstrates/proves that…" | "The included evidence indicates that…", calibrated to GRADE |
| **Tense** | mixed | Past for what the review did and what studies found ("Four studies reported…"); present for what the evidence now indicates and what tables show ("Table 2 summarises…") |

## General patterns (remove the AI voice)

| # | Pattern | Before | After |
| --- | --- | --- | --- |
| 1 | Significance inflation | "marks a pivotal moment for the field" | state what changed, with a date or number |
| 3 | Superficial -ing tails | "…, highlighting the importance of X" | cut, or make it a sourced sentence |
| 4 | Promotional language | "a groundbreaking, cutting-edge approach" | describe what the approach does |
| 5 | Vague attribution | "Experts believe…", "It is well known that…" | cite the studies, or delete |
| 6 | Formulaic challenges | "Despite challenges, the field continues to grow" | name the limitation and its consequence |
| 7 | AI vocabulary | delve, tapestry, testament, landscape, underscore, showcase, pivotal, intricate, multifaceted, realm, paramount, seamless, holistic, leverage | plain verbs and nouns |
| 8 | Copula avoidance | "serves as", "stands as", "boasts" | "is", "has" (technical verbs such as "measures" or "contains" are fine) |
| 9 | Negative parallelism | "not just X, but Y" | state Y |
| 11 | Synonym cycling | "participants… subjects… individuals…" | one term, repeated |
| 13 | Em dash as connector | "…was limited — studies were small — and…" | commas or separate sentences; at most one parenthetical dash per paragraph |
| 17 | Emojis, decorative symbols | 🚀, ✨ | none |
| 19 | Chatbot artifacts | "I hope this helps", "Certainly!", "Here is the synthesis" | delete |
| 20 | Knowledge-cutoff disclaimers | "Based on available information…" | delete; the review states its search dates |
| 22 | Filler | "in order to", "due to the fact that", "it is important to note that" | "to", "because", (delete) |
| 23 | Stacked hedges | "may potentially suggest" | one hedge: "suggests" or "may indicate" |
| 24 | Generic conclusions | "paves the way", "holds great promise", "the future looks bright" | the specific gap and the study design that would close it |

## Formal scientific register

| # | Pattern | Before | After |
| --- | --- | --- | --- |
| 25 | Causal overclaim | "proves", "confirms that" | "is consistent with", sized to the design |
| 27 | Hype adjectives | "novel, robust, unprecedented" | what is new, measured ("robust" only in its statistical sense) |
| 28 | Generalising past the sample | "works for adolescents" | "in four studies of adolescents aged 12–17 (n = 1,204)" |
| 29 | Unquantified magnitude | "improved substantially" | "improved from 0.71 to 0.84 (AUROC)" |
| 31 | Vague quantifiers | "several", "numerous", "a number of" | the count |
| 32 | Numeric style | "p=.03", "5mg", "~10 fold" | "p = 0.03", "5 mg", "10-fold" |
| 33 | Anthropomorphised data | "the data tell us", "the model believes" | "the data indicate", "the model assigns" |
| 34 | Dangling "this" | "This suggests…" | "This difference in follow-up suggests…" |
| 35 | Open lists | "anxiety, sleep, etc." | name all, or "including" plus the full list in a table |
| 37 | Conversational register | contractions, "looked into", "a lot of", "pretty close" | "did not", "examined", "many" → the count, "within 4%" |
| 38 | Reader address, rhetorical questions | "What does this mean for you?" | a statement of the implication |

**Where the scientific register overrides the general pass.** One deliberate
hedge ("suggests", "may reflect") is precision, not padding; GRADE requires
one at moderate certainty and below. Three-item lists are fine when there are
three arms, outcomes or datasets. Follow the target journal's style sheet for
heading case and quote marks.

## Example

**Before**

> This comprehensive review delves into the multifaceted landscape of vocal
> biomarkers for depression. Numerous studies have shown that acoustic
> features play a crucial role in detection — highlighting the transformative
> potential of speech analysis. Moreover, the evidence significantly
> underscores that these methods could potentially revolutionize clinical
> practice, paving the way for exciting future research.

**After**

> This review examined acoustic and prosodic speech features as markers of
> depression. Fourteen of the 19 included studies reported classification
> accuracy, with AUROC values from 0.68 to 0.91; 11 used samples under 100
> participants, and none validated a model in an external cohort. Speech
> features may distinguish people with depression from controls (low
> certainty, downgraded for risk of bias and imprecision). Clinical
> application has not been evaluated; a prospective study with external
> validation would be required.

## The revision pass

1. `python scripts/check_writing.py out/review.json`. It writes
   `review.writing.md` with every flagged sentence, its location and the
   pattern.
2. Rewrite each flagged sentence **in `review.json`**, following the rules
   above and the "never restyle" list. Read the surrounding paragraph: the
   checker sees sentences, not argument.
3. Read the whole prose once more for what no regex catches: synonym cycling,
   claims sized past their GRADE rating, missing "not assessed" statements, a
   result reported without its study count.
4. Re-run the checker until it reports no errors, then re-export and re-run
   `verify_citations.py` (a rewrite can disturb a citation).
