# Review manuscript template

The section plan every SynthScholar review manuscript follows.
`scripts/assemble_manuscript.py` renders it, and `--check` enforces its gates.
It merges two sources: the SynthScholar resource-mapping template (gates,
budgets, the 50-page appendix policy) and the general literature-review
template from claude-code-templates (`literature-review/assets/review_template.md`,
for effect reviews: study characteristics, thematic synthesis, meta-analysis,
GRADE).

**Two variants.** Choose with `review_type` in `review.manuscript.json`:

- **`effect`** (default): systematic reviews whose unit is the *study*: PRISMA
  2020, risk of bias, synthesis by theme, meta-analysis when done, GRADE.
- **`mapping`**: scoping reviews, systematic maps and **resource surveys**
  whose primary unit is a *system* (a knowledge graph, tool, platform, dataset
  or model), with publications as the secondary unit: PRISMA-ScR, the
  resource inventory, a confidence statement instead of GRADE.

They differ only where marked **[effect]** / **[mapping]**.

**Hard length policy: at most 50 pages** (`page_limit`). The budget below
spends those pages on a manuscript, and everything per-record moves to
sibling files. A 4 MB `review.md` whose body is 4% of the file is not a long
review: it is a short review with a dataset stapled to it.

**Rule for the whole document: every heading below is emitted, in this
order, with no numbering gaps.** A section with no data emits its heading
plus one explicit sentence, "Not assessed: <reason>", never nothing.

Each section lists:
- **Source**: the `review.json` field, or the `review.manuscript.json` field
  (`ms.`) that you author.
- **Content**: what it must contain, in the review's own numbers.
- **Budget**: target words, scaled to `protocol.word_count_target`
  (percentages assume 10,000).
- **Gate**: the condition for the section to count as written. A failed
  gate is reported at `--check`; it is never a silent empty heading.

The prose follows [writing_style.md](writing_style.md) throughout.

---

## Front matter (unnumbered)

**Source:** `protocol`, `timestamp`, `review_id`, `flow`
**Budget:** 100
**Gate:** registration present (an ID, or the literal "Not registered"),
and the reading-basis line present.

```
# [Title]

**Review type:** [Systematic review / Scoping review / Systematic map / Resource survey]
**Protocol:** [version, date or URL] | **Registration:** [ID / Not registered]
**Searches executed:** [YYYY-MM-DD] | **Review id:** [review_id] | **Generated:** [timestamp]
**Unit of analysis:** [N] included studies   ([mapping]: [N] unique resources described in [M] publications)
**Reading basis:** [F] of [M] publications read in full text, [A] on the abstract only
**Analysis:** [models / agents used; human verification performed — one line]
```

The reading-basis line belongs on the front page, not only in the limitations.

## Abstract (unnumbered)

**Source:** `ms.abstract` (else `structured_abstract`)
**Budget:** 300
**Gate:** at least 250 words, every label non-empty, and it states the
included count, the reading basis and at least three headline numbers.

Labels, in order:
- **Background**
- **Objectives**
- **Methods**: sources, date range, selection, charting, appraisal.
- **Results**: records → included ([mapping]: → unique resources), then the
  three to six strongest cross-cutting numbers.
- **Conclusions**
- **Limitations**: one sentence, reading basis first.
- **Registration**
- **Keywords**: five to eight.

> Failure seen in practice: a 93-word abstract carrying only the flow
> counts. The abstract is what most readers read: it must carry findings,
> not just provenance.

---

## 1. Introduction

**Budget:** 900 (about 9%)

### 1.1 Background and context
**Source:** `ms.introduction.background`
**Content:** what the topic or resource class is, why it matters, and what
changed recently.
**Gate:** at least 400 words, and not a restatement of the objective.

### 1.2 Prior reviews and what this review adds
**Source:** `ms.prior_reviews` (`{citation, scope, year_cutoff, gap_addressed}`)
plus `ms.introduction.prior_reviews_text`.
**Content:** each prior review, with its scope and cutoff, and this
review's specific contribution.
**Gate:** at least one prior review, or an explicit "No prior review
identified; searched as <query>".

### 1.3 Objectives and research questions
**Source:** `protocol.objective`, `protocol.research_questions`
**Content:** the objective, then a table: ID | question | where answered.
**Gate:** every research question maps to a Results subsection.

### 1.4 Scope boundary
**Source:** `ms.introduction.scope`
**Content:** what is deliberately out of scope, and why.
**Gate:** present.

### 1.5 Terminology
**Source:** `ms.introduction.terminology` (`{term: definition}`)
**Content:** the 5 to 15 terms used in a specific sense, including coding
vocabulary and NR / NA / Unverified.
**Gate:** every coded category label used in a Results table appears here
or in Appendix E.

---

## 2. Methods

**Source:** `protocol`, `search_queries`, `flow`, plus `ms.methods.*`
**Budget:** 1,200 (about 12%)

| Sub | Heading | Source | Gate |
|---|---|---|---|
| 2.1 | Protocol, registration and deviations | `protocol.amendments` | deviations listed, or "none" |
| 2.2 | Eligibility criteria | `protocol.inclusion_criteria` / `exclusion_criteria` | a two-column table, not a run-on paragraph |
| 2.3 | Information sources | `protocol.databases`, `ms.methods.sources` | per source: interface, records returned, date run |
| 2.4 | Search strategy | `search_queries` | the full query per source, verbatim, in a fenced block |
| 2.5 | Selection process | `screening_log`, `flow`, `ms.methods.selection` | who or what screened, single or dual, the conflict rule, inclusive title/abstract versus strict full text |
| 2.6 | Full-text retrieval and reading basis | `flow.full_text_sources` | the route table, why reports were not retrieved, and whether paywalled access was tried |
| 2.7 | Data charting | `protocol.charting_questions`, `ms.methods.charting` | item count and group names; pilot and harmonisation rules |
| 2.8 | Unit of analysis | `ms.dedup_rule` | [mapping] how multi-publication systems were collapsed, with counts; [effect] how multiple reports of one study were linked |
| 2.9 | Cross-study coding | `ms.coding_methods` | for each derived category: the rule, the script, and "per-record answers are authoritative" |
| 2.10 | Critical appraisal | `protocol.rob_tool`, `protocol.appraisal_domains` | the instrument, its adaptation, the domains, and how abstract-only records were rated |
| 2.11 | Synthesis approach | `ms.methods.synthesis` | [effect] narrative and/or meta-analysis (model, heterogeneity, sensitivity); [mapping] descriptive counting, stating each time whether a count is of publications or resources |
| 2.12 | Independent verification | `ms.verification` + citation report | citation and URL checks, their dates, and what they do *not* establish |

---

## 3. Results

**Budget:** 3,800 words of prose (about 38%), excluding tables.

### 3.1 Selection and flow
**Source:** `flow`, plus the **PRISMA 2020 flow diagram** (figure `prisma`)
**Gate:**
- the diagram;
- identification per source;
- exclusion reasons with counts at both stages;
- the reading-basis table.

### 3.2 Descriptive overview
**Source:** `included_articles`, figures `years` and `designs`, `ms.results.overview`
**Budget:** 350
**Content:**
- publications per year, with the inflection named;
- venue and publication type;
- the preprint share;
- the source overlap.

**Gate:** each figure is named in the text by number, with one sentence of
interpretation.

### 3.3 [effect] Study characteristics / [mapping] Resource inventory
**Source:** [effect] `included_articles` + `extracted_data`; [mapping]
`ms.resource_catalog`
**Budget:** 400
**Content:**
- [effect] a table with one row per study: study, year, design, sample,
  population, outcomes, appraisal concern.
- [mapping] the deduplicated inventory: resource, year, developer,
  domain, representation, availability, maintenance and publication count.
  A short lead says how many resources more than one publication
  describes, which are the oldest and newest, and which are still
  reachable.

**Gate:**
- one row per study or resource;
- verified columns are distinguished from author-reported ones;
- above 60 rows, an extract inline plus "Complete table: `<file>` (N rows)".

### 3.4 … 3.n One subsection per research question
**Source:** `ms.results.rq[<question_id>]` (else the per-question answers in
`review.json`)
**Budget:** 400 to 500 each

Each subsection has this fixed shape, in protocol order:

```
### 3.x RQ[n] — [theme]
[Lead paragraph: the single most important pattern, with its number.]
[Distribution table or figure, with counts AND denominators.]
[Figure N named, with one interpretive sentence.]
[Contrasts: which subgroups, years or domains differ, with numbers.]
[Named exemplars: three to eight studies or systems, by name.]
[Negative space: what is absent or unreported, with the NR count.]
[Caveat: denominator, coding rule, abstract-only share.]
```

**Gate:**
- at least one quantitative claim with its denominator;
- at least three named studies or resources;
- the NR count;
- at least 250 words.

**Pre-filled when not yet written.** If `ms.results.rq.<id>` is empty, the
subsection is filled from the charted answers in `review.json`. It gets a
factual opening line ("Answers were charted for k of n included studies; m
did not report it"), then one row per study with its answer, and every
answer goes to `review.rq-<id>.csv`. Nothing is summarised or inferred. The
gate `rq-unsynthesised` stays until the synthesis itself is written.

**[effect]** When the review has no research questions, there is one
subsection per synthesis theme. Each covers findings across studies (never
study by study), the supporting studies, contradictory evidence, and the
certainty.

### 3.n+1 [effect] Meta-analysis / [mapping] Cross-cutting comparison
**Source:** `ms.results.meta_analysis` / `ms.results.cross_cutting`
**Budget:** 400
**Content:**
- [effect] pooled estimates with 95% CI, heterogeneity (I², τ²),
  subgroup and sensitivity analyses, publication bias, forest plots.
- [mapping] the capability matrix read across categories: which profiles
  co-occur and which groups lead or lag.

**Gate:** [effect] if not performed, "Not performed: <reason>"; [mapping]
at least two profiles contrasted.

### 3.n+2 Per-group analysis
**Source:** `per_group_analysis`, figure `groups`, `ms.results.groups_lead`
**Budget:** a 150-word lead plus the generated blocks.
**Gate:** the lead compares the groups (largest, fastest-growing,
best-evaluated); the per-group blocks are not the section's only content.

### 3.n+3 Critical appraisal
**Source:** `structured_appraisal_results`, figure `appraisal`, `ms.results.appraisal`
**Budget:** 350
**Gate:**
- a domain × concern table over all records;
- the items that drove concern;
- concern by reading basis, with abstract-only inflation quantified.

### 3.n+4 Certainty / confidence in the synthesis
**Source:** [effect] `grade_assessments`; [mapping] `ms.confidence_statement`
**Budget:** 200
**Gate:** "Not assessed" alone fails.
- [effect] a GRADE row per outcome, with downgrading reasons.
- [mapping] a statement per dimension: completeness of identification,
  reporting completeness, coding reliability, verification depth. Each is
  rated, with a reason.

### 3.n+5 Knowledge and capability gaps
**Source:** `ms.gaps` (`{gap, evidence, affected_groups, severity}`)
**Budget:** 500
**Content:** gaps as findings, each tied to its evidence. Keep three kinds
apart:
- limitations the authors acknowledged, aggregated;
- gaps visible only in the cross-study data;
- domains, species or tasks with nothing at all.

**Gate:**
- at least five gaps, each with a number;
- absence of reporting is never presented as absence of capability without
  saying so.

---

## 4. Discussion

**Source:** `ms.discussion.*`
**Budget:** 2,200 (about 22%)
**Gate:** every subsection below non-empty.

| Sub | Heading | Content | Budget |
|---|---|---|---|
| 4.1 | Principal findings | one paragraph per RQ, answering it in a sentence with its supporting number | 500 |
| 4.2 | Interpretation | why the evidence looks like this: incentives, tooling, data availability, funding, standards maturity, mechanisms | 400 |
| 4.3 | Comparison with prior reviews | agreement and disagreement with §1.2, and what changed since their cutoffs | 250 |
| 4.4 | Implications | separately for practice, policy, and developers or standards bodies | 400 |
| 4.5 | Research agenda | five to eight prioritised directions, each with rationale, approach and what success looks like | 400 |
| 4.6 | Strengths | coverage, unit-of-analysis rigour, verification, open data | 100 |
| 4.7 | Limitations | `limitations` plus `ms.discussion.limitations`, ordered: reading basis, reviewer independence, search coverage, coding reliability, verification depth, currency | 300 |
| 4.8 | Reflexivity on automated authorship | which stages a model performed, what humans verified, and what that means for the claims | 150 |

> A Discussion that is only a Limitations list is not a Discussion.

---

## 5. Conclusions

**Source:** `ms.conclusions` (a list), else `conclusions_text`
**Budget:** 350
**Gate:**
- non-empty, as its own numbered section;
- three to six numbered conclusions, each answering a stated RQ;
- a final line giving the evidence certainty [effect] or the maturity
  verdict [mapping], plus translation readiness.

---

## 6. Declarations

**Source:** `protocol.funding_sources`, `competing_interests`,
`registration_number`, `ms.declarations`
**Budget:** 200
**Gate:** every row present; "NR" only after a real check.

The rows:
- Registration and protocol availability
- Funding
- Competing interests
- Data and code availability: every exported dataset, by filename
- AI-assistance statement: models, roles, verification
- Contributions
- Acknowledgements

---

## References (unnumbered)

**Source:** `included_articles`, or `<stem>.references.<style>.md` from
`verify_citations.py --style`.
**Gate:**
- the style matches `protocol.citation_style`;
- every entry is verified or flagged unverified;
- retractions are reported;
- every entry is cited by its peer-reviewed DOI, with its PMID where
  PubMed has it (preprints only when no published version exists, and
  labelled as such);
- in-text citations resolve to this list.

Cite included works in the body by author–year or a stable key, never by
bare PMID. A body that cites raw identifiers reads as a dataset dump, not
a manuscript.

---

## Appendices

| ID | Appendix | Source | Inline (`appendix_policy: sibling`) | Sibling file |
|---|---|---|---|---|
| A | Search strings per source, with date and count | `search_queries` | full | — |
| B | PRISMA 2020 / PRISMA-ScR checklist, mapped to sections | `ms.checklist` | full | — |
| C | Excluded at eligibility, with reasons | `screening_log` | reason counts | `review.screening.md` |
| D | Appraisal detail, study × domain | `structured_appraisal_results` | domain × concern summary | `review.appraisal.md` |
| E | Charting form: items and value vocabulary | `protocol.charting_questions` | item list | `protocol.json` |
| F | Evidence spans | `evidence_spans` | none (cite inline instead) | `review.evidence.md` |
| G | Per-question charting tables | generated | none | `review.charting.md` |
| H | URL and repository verification | `ms.verification.urls` | counts | `url_verification.json` |
| I | Citation verification | citation report | counts | `review.citations.md` |
| J | [mapping] Resource ↔ publication map | `ms.resource_catalog` | none | `resource_catalog.csv` |

Each inline appendix ends with a one-line pointer: "Full table:
`review.charting.md` (N rows)". The rule for per-question charting is one
question, one table, one row per study, never the same table repeated once
per research question. `appendix_policy: inline` is for corpora under about
40 studies only.

## Supplementary datasets (unnumbered)

A table of every exported file, with a one-line description and its unit of
analysis: per publication, per resource, per decision or per URL.
**Gate:** counts quoted in the body reconcile with these files. A headline
number in a README that disagrees with the manuscript blocks export.

---

## Figures: where a human author would put them

A figure earns its place when it shows a pattern the text then discusses.
`scripts/review_figures.py` draws the standard set from the data, and only
when the data supports it:

| Figure | Section | Drawn when |
|---|---|---|
| PRISMA 2020 flow diagram | 3.1 | always, given flow counts |
| Publications per year | 3.2 | at least 3 distinct years |
| Study designs | 3.2 | at least 2 known designs |
| Studies per group | per-group analysis | at least 2 groups |
| Appraisal concern per domain | critical appraisal | at least 3 studies appraised |
| Reading basis / retrieval routes | 2.6 | at least 2 routes, or any abstract-only |
| Forest plot [effect], capability heat-map [mapping] | meta-analysis / cross-cutting | supplied by you (`ms.figures`) |

Rules:

- **Numbered in order of first appearance**, with a caption in the form
  "**Figure N.** caption". The assembler numbers them, so never hard-code a
  number.
- **Each figure is discussed in its section's prose.** Refer to it as
  `{fig:<id>}` (rendered as "Figure N"), with at least one sentence
  interpreting it from its `facts` in `figures.json`. A figure with no
  reference and no `ms.figures.<id>.interpretation` fails the gate.
- **Ten to twelve figures at most** (about 0.4 page each). No decorative
  charts, and no chart that only repeats a table already shown.
- **Your own figures** (a forest plot, a capability matrix) go in
  `ms.figures` as `{id, file, caption, section, interpretation}`. Images
  are scaled to the page; none is cut off.

---

## Page and word budget (50-page cap)

Prose budget, excluding tables and figures, at `word_count_target` (10,000):

| Part | % | Words |
|---|---|---|
| Abstract | 3 | 300 |
| Introduction | 9 | 900 |
| Methods | 12 | 1,200 |
| Results | 38 | 3,800 |
| Discussion | 22 | 2,200 |
| Conclusions | 3.5 | 350 |
| Declarations and front matter | 3 | 300 |
| Figure and table interpretation | 9.5 | 950 |

Page allocation for the rendered PDF:

| Block | Pages |
|---|---|
| Front matter and abstract | 1.5 |
| Introduction | 2 |
| Methods | 4.5 |
| Results prose | 8 |
| Figures (10–12 at about 0.4 page) | 4.5 |
| Main tables | 6 |
| Discussion and conclusions | 5.5 |
| Declarations | 0.5 |
| References | 11 |
| Inline appendices A–D | 6 |
| **Total** | **about 50** |

Estimate the pages before writing:

```
pages ≈ words/550 + 0.4·figures + table_rows/45 + 0.045·references
```

Two consequences for large corpora:

1. **Above about 60 rows, §3.3 is sampled inline and complete in the
   sibling file.** Above about 120, render group-level summary rows only.
2. **References scale with the corpus.** Beyond about 400, keep only
   cited-in-body works inline and move the full list to
   `review.references.<style>.md`.

Below 70% of the word target, sections were skipped. Above the page limit,
per-record material is still inline: fix that by moving appendices out,
never by cutting the Discussion.

## Export gates (`assemble_manuscript.py --check`)

**Failures (exit 1):**
1. A declared heading is missing, or the numbering skips.
2. Conclusions are empty, or the Discussion holds only limitations.
3. The estimated page count exceeds `page_limit`.

**Warnings:**
4. Body prose below 70% of `word_count_target`.
5. A figure is placed but not referenced, or has no interpretation.
6. A research question has no Results subsection, or one under 250 words.
7. [effect] No GRADE and no certainty statement; [mapping] no confidence
   statement.
8. The abstract is under 250 words, or missing a label.
9. Appendices exceed 20% of the pages, or a per-record appendix (F, G, H,
   J) is inline under the sibling policy.
10. The reading basis is absent from the front matter, abstract or
    limitations.
11. A sibling file is referenced but missing from the output directory.
12. The prior-reviews subsection is empty without a "none identified"
    statement.
13. Fewer than five gaps, or a gap without a number.
14. Bare-PMID citations in the body.

## `review.manuscript.json`: the sections you author

The data stays in `review.json`. The prose that turns it into a paper goes
here, in one file beside it:

```json
{
  "review_type": "effect",
  "settings": {"page_limit": 50, "appendix_policy": "sibling", "word_count_target": 10000},
  "front_matter": {"review_type_label": "Systematic review", "searches_executed": "2026-05-01",
                   "analysis": "Screening, charting and appraisal by Claude; citations verified by script; synthesis checked by the first author."},
  "abstract": {"background": "", "objectives": "", "methods": "", "results": "",
               "conclusions": "", "limitations": "", "registration": "", "keywords": []},
  "introduction": {"background": "", "prior_reviews_text": "", "scope": "", "terminology": {}},
  "prior_reviews": [{"citation": "", "scope": "", "year_cutoff": "", "gap_addressed": ""}],
  "methods": {"sources": "", "selection": "", "charting": "", "synthesis": ""},
  "dedup_rule": "", "coding_methods": [{"category": "", "rule": "", "script": ""}],
  "verification": {"summary": "", "urls": {}},
  "results": {"overview": "", "characteristics_lead": "",
              "rq": {"RQ1": "… {fig:years} shows …"}, "themes": {},
              "meta_analysis": "", "cross_cutting": "", "groups_lead": "", "appraisal": ""},
  "resource_catalog": [],
  "confidence_statement": "",
  "gaps": [{"gap": "", "evidence": "", "affected_groups": "", "severity": ""}],
  "discussion": {"principal_findings": "", "interpretation": "", "comparison": "",
                 "implications": "", "research_agenda": "", "strengths": "",
                 "limitations": "", "reflexivity": ""},
  "conclusions": [""], "certainty_verdict": "", "translation_readiness": "",
  "declarations": {"funding": "", "competing_interests": "", "data_availability": "",
                   "ai_assistance": "", "contributions": "", "acknowledgements": ""},
  "checklist": [{"item": "1 Title", "section": "Title"}],
  "figures": {"years": {"interpretation": ""}}
}
```

Fields left empty fall back to what `review.json` holds (the pipeline's
introduction, synthesis themes, limitations, GRADE). Where neither has
content, the heading is still emitted, with "Not assessed: <reason>", and
the gate reports it.
