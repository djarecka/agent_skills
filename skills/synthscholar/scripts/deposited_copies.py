"""Repository-deposited copies: the last full-text route.

Used only after the published version could not be retrieved, by open access
or through the user's institutional proxy, and after its registry-linked
preprint (if any) also missed. Authors often deposit a copy elsewhere:

* **Zenodo** — exact-title search through its public records API; any copy
  (accepted manuscript, preprint or the published PDF) an author uploaded.
* **arXiv** — exact-title search through its public API (paced to its one
  request per three seconds; a rate-limit reply is a miss, not an error).

A candidate is accepted only when its title matches the paper's (≥ 0.90
normalised similarity) **and** its first author's surname matches, and the
download really is a PDF (``%PDF-`` magic bytes). Whatever is read here is a
deposited copy, not the version of record, so it is labelled as such
(``zenodo_pdf`` / ``arxiv_pdf``) and the paper is still cited by its published
DOI.

Sites without an API that permits automated access (ResearchGate, Academia.edu)
are deliberately not queried.
"""
from __future__ import annotations

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_citations import TITLE_MATCH, surname_matches, title_similarity  # noqa: E402

SOURCE_ZENODO = "zenodo_pdf"
SOURCE_ARXIV = "arxiv_pdf"
ZENODO = "https://zenodo.org/api/records"
ARXIV = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_INTERVAL = 3.1   # arXiv API terms: at most one request every three seconds


class DepositFinder:
    def __init__(self, mailto: str = "", timeout: float = 30.0):
        ua = "synthscholar-skill-deposited-copies/1.0" + (f" (mailto:{mailto})" if mailto else "")
        self.http = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": ua})
        self._last_arxiv = 0.0

    def close(self) -> None:
        self.http.close()

    # ── public ──

    def fetch(self, title: str, authors: str) -> Optional[tuple[bytes, str, str]]:
        """``(pdf bytes, source, url)`` of the first verified deposited copy, or None."""
        if len(title.split()) < 3 or not authors.strip():
            return None   # too little to verify a match by; never guess
        for find in (self._zenodo, self._arxiv):
            for url, source in find(title, authors):
                data = self._pdf(url)
                if data:
                    return data, source, url
        return None

    # ── sources ──

    def _matches(self, cand_title: str, cand_first_author: str, title: str, authors: str) -> bool:
        return (title_similarity(title, cand_title) >= TITLE_MATCH and bool(cand_first_author)
                and surname_matches(cand_first_author, authors))

    def _zenodo(self, title: str, authors: str) -> list[tuple[str, str]]:
        q = 'title:"' + title.replace('"', " ").strip() + '"'
        try:
            r = self.http.get(ZENODO, params={"q": q, "size": 5})
            hits = (r.json().get("hits") or {}).get("hits") or [] if r.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            return []
        out = []
        for h in hits:
            m = h.get("metadata") or {}
            if (m.get("access_right") or "open") != "open":
                continue
            creators = m.get("creators") or []
            name = (creators[0].get("name") or "").strip() if creators else ""
            # "Family, Given" — or "Family G.A." with no comma: the first word
            fam = name.split(",")[0].strip() if "," in name else (name.split() or [""])[0]
            if not self._matches(m.get("title", ""), fam, title, authors):
                continue
            for f in h.get("files") or []:
                if (f.get("key") or "").lower().endswith(".pdf"):
                    link = (f.get("links") or {}).get("self", "")
                    if link:
                        out.append((link if link.endswith("/content") else link + "/content",
                                    SOURCE_ZENODO))
        return out

    def _arxiv(self, title: str, authors: str) -> list[tuple[str, str]]:
        wait = ARXIV_INTERVAL - (time.monotonic() - self._last_arxiv)
        if wait > 0:
            time.sleep(wait)
        self._last_arxiv = time.monotonic()
        q = 'ti:"' + title.replace('"', " ").strip() + '"'
        try:
            r = self.http.get(ARXIV, params={"search_query": q, "max_results": 5})
            root = ET.fromstring(r.text) if r.status_code == 200 else None
        except (httpx.HTTPError, ET.ParseError):   # "Rate exceeded." is plain text
            return []
        out = []
        for e in (root.findall("a:entry", ATOM) if root is not None else []):
            t = " ".join((e.findtext("a:title", "", ATOM) or "").split())
            first = e.find("a:author/a:name", ATOM)
            fam = (first.text or "").split()[-1] if first is not None and first.text else ""
            if not self._matches(t, fam, title, authors):
                continue
            pdf = next((ln.get("href") for ln in e.findall("a:link", ATOM) if ln.get("title") == "pdf"), "")
            if pdf:
                out.append((pdf.replace("http://", "https://", 1), SOURCE_ARXIV))
        return out

    def _pdf(self, url: str) -> Optional[bytes]:
        try:
            r = self.http.get(url)
        except httpx.HTTPError:
            return None
        return r.content if r.status_code == 200 and r.content[:5] == b"%PDF-" else None


def authors_string(meta_authors: list[tuple[str, str]]) -> str:
    """Registry ``[(family, given)]`` → ``"Family G, Family G"`` for matching."""
    return ", ".join(f"{fam} {given[:1]}".strip() for fam, given in meta_authors if fam)

