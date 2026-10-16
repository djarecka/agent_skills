# Citation verification

A generated review is only as trustworthy as its citations. The LLM grounding
pass (`grounding_validation`) asks a model whether claims are supported; it does
not ask a registry whether a DOI exists, whether it belongs to the paper the
review names, or whether that paper was retracted. `scripts/verify_citations.py`
does that deterministically, and also checks that every study the prose cites is
one the review actually included.

```bash
python scripts/verify_citations.py out/review.json                      # gate
python scripts/verify_citations.py out/review.json --apply out/review.verified.json
python scripts/verify_citations.py out/review.json --style vancouver    # + reference list
python scripts/verify_citations.py out/review.json --offline            # no network
python scripts/verify_citations.py manuscript.md --check-urls           # any Markdown
```

Output: `<base>.citations.md` (show this to the user), `<base>.citations.json`
(machine-readable, every registry record it compared against). Exit `0` = no
errors, `1` = errors (or warnings under `--strict`), `2` = bad input.

Set `SYNTHSCHOLAR_EMAIL` (or `--mailto`): Crossref's polite pool and NCBI both
want a contact address. `NCBI_API_KEY` raises the PubMed rate limit. Cost is
about two Crossref requests per DOI plus one batched PubMed call per 200 PMIDs;
`--no-retraction-check` halves the Crossref part, at the price of missing
retractions.

## What is checked

### Reference metadata (each included article)

| Identifier | Registry | Compared |
| --- | --- | --- |
| DOI | Crossref `/works/{doi}`; if absent there, the doi.org handle server, then CSL-JSON content negotiation (DataCite, mEDRA, …) | title (normalised similarity), first author's surname, year (any of issued / print / online / posted) |
| DOI | Crossref `updated-by` **and** `filter=updates:{doi}` | retraction, withdrawal, expression of concern, correction notices pointing at the paper |
| PMID | NCBI E-utilities `esummary`, batched | exists, title, PubMed's DOI vs the claimed DOI, `Retracted Publication` |
| none | Crossref `query.bibliographic` | proposes a DOI *candidate*: title ≥ 0.90 similar **and** first author matches **and** year within 1 |

BYO-corpus ids (`local_…`) are not PMIDs and are skipped for PubMed.

**Why retractions are read from the paper's side.** A Crossref retraction
notice carries `update-to` pointing at the retracted paper; the paper itself
carries `updated-by` (and is returned by the `updates:` filter). A checker that
reads only `update-to` on the cited DOI flags cited *notices* and misses every
cited retracted *paper*, which is the case that matters.

### In-text citations (the generated prose)

Every string in the review result except its inputs and logs (`included_articles`,
`screening_log`, `protocol`, search/run metadata) is scanned: synthesis,
introduction, discussion, GRADE, bias assessment, per-group answers, narrative
rows, and structured id fields (`paper_pmid`, `*_pmids`). Evidence spans
are quotes from the source papers, so only their `paper_pmid` is checked; a
citation inside a quote belongs to that paper's own reference list.

| Citation form | Must |
| --- | --- |
| `PMID: 123`, `PMIDs: 12345, 67890`, `PMID: local_ab12cd34`, `*_pmids` lists | be an included article (list items after the first must look like PMIDs, 5+ digits, so "PMID: 123, 2019 cohort" reads one PMID) |
| a DOI | be an included article's DOI |
| `(Smith et al., 2023)`, `Smith et al. (2023)` | match an included article's first author and year (±1) |
| `(Smith et al., 2023; PMID: 123)` | the author–year must belong to PMID 123 |

Month names and words like *since*, *phase*, *wave*, *table* before a year are
not treated as surnames.

## Severity, and what to do about each finding

The rule underneath all of these: **never resolve a finding by inventing
metadata, and never "fix" a citation by editing the prose to match a wrong
reference.** Fix the reference from the registry, or remove the claim.

| Code | Severity | Meaning | Action |
| --- | --- | --- | --- |
| `doi-not-found` | error | DOI registered nowhere | typo or fabrication. Re-read the PDF's first page for the real DOI. If it has none, clear the field (`build_corpus.py`'s rule: empty beats guessed) |
| `doi-invalid` | error | not DOI-shaped | as above |
| `doi-title-mismatch` | error | DOI belongs to a different paper | replace with the PDF's DOI, or a `doi-candidate` the user confirms. The prose may be fine; the identifier is wrong |
| `pmid-not-found`, `pmid-title-mismatch` | error | PMID wrong | correct from the PDF / PubMed search; BYO entries without a real PMID keep their `local_` id |
| `pmid-doi-conflict` | error | PubMed's DOI ≠ claimed DOI | one of the two is wrong; the title-matching one wins |
| `retracted` | error | retracted / withdrawn / removed | **tell the user.** A retracted study normally leaves the synthesis: re-run screening with the retraction as the exclusion reason, or justify keeping it explicitly in the limitations. Never drop it silently |
| `cites-notice` | error/warning | the DOI is a retraction or correction notice, not a study | point the reference at the original paper |
| `citation-excluded` | error | prose cites a study the screening log excluded | remove or rewrite the claim. The excluded study's evidence must not support the synthesis |
| `citation-unknown` | error | prose cites an id that appears nowhere in the review | hallucinated citation: remove the claim or re-attribute it to the included study that actually supports it (check its evidence spans) |
| `doi-title-partial`, `doi-author-mismatch`, `doi-year-mismatch` | warning | close but not exact | read the registry record in the JSON report; usually the review's metadata needs correcting |
| `author-year-pmid-conflict` | warning | "(Smith 2019; PMID: X)" but X is Harris 2020 | fix whichever half is wrong |
| `author-year-unmatched` | warning | author–year citation matching no included study | as `citation-unknown`, unless it is background literature deliberately cited in the introduction. Say so if it is |
| `update-expression_of_concern`, `update-partial_retraction` | warning | editorial concern | mention it in the limitations / risk-of-bias text |
| `doi-missing` | warning | nothing to verify against | look for a `doi-candidate`; otherwise leave it |
| `doi-malformed` | warning | URL prefix / trailing punctuation in the DOI field | `--apply` fixes it |
| `duplicate-doi` | warning | two included entries share a DOI | the same study included twice: merge them, and fix the PRISMA counts |
| `lookup-failed` | warning | network / registry error | re-run; unverified ≠ verified |
| `doi-candidate` | info | Crossref title match for a DOI-less or mismatched entry | **confirm before using**: show the user, or check it against the PDF. Never applied automatically |
| `doi-from-pubmed` | info | DOI filled from a verified PMID | applied by `--apply` |
| `update-correction` etc. | info | a correction exists | no action; corrections do not invalidate a study |
| `doi-year-offby1` | info | online vs print year | no action |
| `preprint-has-published-version` | warning | the cited preprint has a registry-linked peer-reviewed version (the journal article's `has-preprint`, or the preprint's `is-preprint-of`) | cite the published version (`--apply` switches DOI, journal, year, title), then **re-check the extracted numbers against the published text**: results can change in peer review |
| `preprint-published-candidate` | warning | a journal article matches the preprint by title, first author and year, but no registry link exists | confirm it is the same work, then cite it. Never applied automatically |
| `preprint-only` | info | a preprint with no peer-reviewed version found | keep it, labelled; state in the limitations that it is not peer-reviewed |
| `pmid-found` | info | PubMed has the article (looked up by DOI, title confirmed) | `--apply` records the PMID |
| `duplicate-study` | error | two included entries are one work (a preprint and its published version) | one study counted twice: keep the published one, exclude the other, correct the PRISMA counts. Neither entry is switched |
| `uncited-included` | info | included but never cited in the prose | expected for some; many of them means the synthesis ignores part of the corpus |

## `--apply`: what it changes, and what it never does

Writes a corrected copy (the input is never modified) containing only
registry-confirmed changes:

- DOI field normalised (`https://doi.org/10.x/y.` → `10.x/y`);
- empty `title` / `year` / `journal` / `authors` filled from a DOI record whose
  title matched (≥ 0.90). With no title in the review, only when the record's
  first author **and** year both agree: a hallucinated DOI still resolves to
  some real paper;
- a missing DOI filled from PubMed for a PMID whose title matched;
- **a cited preprint switched to its peer-reviewed version** when the registry
  links the two (DOI, journal, year and title from the published record);
- **the PMID recorded** wherever PubMed has the article. The PMID is the
  article's id across the review, so the old id (`local_…`, or a preprint's
  PMID) is rewritten everywhere it appears: the screening log, evidence
  spans, rubrics, per-group lists and `PMID:` citations in the prose. The
  `references_updated` count is in `applied`, and the RDF IRIs change with it.

It never applies a `doi-candidate` or a `preprint-published-candidate`, never
switches an entry flagged `duplicate-study`, never overwrites a non-empty field that
disagrees with the registry (that is a finding for you to judge), and never
touches the prose. Each change is listed under `applied` in the JSON report.

Then re-export from the corrected copy and re-verify:

```bash
python scripts/export_review.py out/review.verified.json --outdir out/ --formats md ttl json
python scripts/verify_citations.py out/review.json
```

A newly filled DOI changes that article's RDF IRI (PMID → DOI → hash), so a
review already ingested into BrainKB is re-ingested, not patched.

## `--style`: reference list from verified metadata

Writes `<base>.references.<style>.md`: `apa` (alphabetical), `nature`,
`vancouver`, `ieee` (numbered in order of first citation in the prose). Entries
whose DOI record matched are rendered from the registry (full author list,
volume, issue, pages, abbreviated journal where Crossref has one). The rest keep
the review's own text and are tagged `[unverified]`. Formats follow the usual
conventions:

| Style | Authors | Shape |
| --- | --- | --- |
| APA 7 | all up to 20, `Family, I. I., & Family, I.` | `Authors (Year). Title. *Journal*, *vol*(issue), pages. https://doi.org/…` |
| Nature | up to 5, else first `et al.` | `Authors Title. *J. Abbrev.* **vol**, pages (year).` |
| Vancouver | up to 6, then `et al` | `Family II, Family II. Title. J Abbrev. Year;vol(issue):pages. doi:…` |
| IEEE | up to 6, else first `et al.` | `I. I. Family, and I. Family, “Title,” *J. Abbrev.*, vol. x, no. y, pp. p, Year, doi: ….` |

The main `review.md` reference list is produced by `synthscholar.export` and is
not rewritten; the styled list is a separate file for a manuscript.

## Reporting to the user

Lead with the errors, by kind, with counts: *"2 DOIs point at different papers,
1 included study is retracted, the synthesis cites 3 PMIDs that are not in the
included set"*. Then say what you changed (from `applied`) and what needs their
decision (`doi-candidate`, retracted studies). Don't call a review's citations
"verified" while `lookup-failed` findings remain.
