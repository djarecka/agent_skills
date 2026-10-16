"""AIT mapping tables -> validated Turtle (the AIT mode's graph deliverable).

`prompts/extractor-cell-type-ait-mapping.md` produces seven CSV tables. This script
turns a validated table set into `<stem>.ttl`: instances of the Named Entity
Ontology, written by the same `json_to_ttl.TurtleBuilder` every NER run uses, so
identity (UUIDv5 keys), provenance and the gate (`validate_ttl.py`) are identical:

* every non-quarantined row of `entities.csv` becomes one `ner:NamedEntity` (cell
  types, genes, species, brain regions), keyed by its normalized label;
* its mentions are the occurrences of `label_verbatim` / `aliases` inside its
  verified evidence spans (grounded), plus, by default, every other in-scope
  occurrence of a surface that belongs to that row alone (`expand_mentions`);
  a surface shared by two rows is never expanded — only its grounded occurrences
  count, each on the row whose evidence holds it;
* every `mappings.csv` edge with an `ait_node_id` becomes `ner:resolvedToConcept` +
  `skos:<relation>` to the node's own IRI in the trusted taxonomy file (read with
  `ait_nodes`, never constructed), with a `ner:ConceptMappingDecision` carrying the
  basis, the mapping evidence, the curator notes and the Pass 4 marker diff; a
  `none` row is recorded as a gap comment with its `no_match_reason`;
* every gene row is linked to its `GeneAnnotation` in the species' trusted genome
  annotation (`ait_nodes.GeneLookup`; catalog `gene_annotations`): exact symbol ->
  `skos:exactMatch`, same symbol in another case or a synonym -> `skos:closeMatch`,
  each with a tool-provenance mapping decision; an ambiguous or unknown symbol, or a
  species with no trusted annotation, is a gap comment and listed in the report;
* every other extracted entity (species, brain regions, cell types without an AIT
  edge) is concept-mapped against the trusted ontologies only
  (`concept_mapping`, sources = trusted: `trusted_ontologes/priority.md` order,
  `label_routing` per class — Species -> NCBITaxon, BrainRegion -> UBERON, CellType
  -> CL > PCL); offline, tool provenance, never from memory. Genes are not sent to
  it: their trusted source is the genome annotation above;
* `entities.marker_genes` become paper-stated `expresses` (RO:0002292) edges when a
  sentence of the paper names both the cell type and the gene (that sentence is the
  evidence); a marker with no such sentence is reported, not written.

The tables must pass `ait_tables validate` first (refused otherwise), and the written
TTL is gated with `validate_ttl` (exit 1 on any violation).

    python -m scripts.ait_ttl out/ --text out/paper.txt --source paper.pdf
    #  -> out/<stem>.ttl  (default stem: paper_id), out/.structsense/<stem>_ait_final.json + kg_plan
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from scripts import ait_nodes, ait_tables  # noqa: E402
import json_to_ttl as j2t  # noqa: E402
from expand_mentions import WS, expand, flex  # noqa: E402
from group_by_entity import mention_groups  # noqa: E402
from rdflib import Literal, URIRef  # noqa: E402
from rdflib.namespace import RDFS, XSD  # noqa: E402

VARIANT = "ait:cell-type-mapping"
GENE_TIER_TO_SKOS = {"symbol": "exactMatch", "symbol_case": "closeMatch", "synonym": "closeMatch"}
CLASS_BY_TYPE = {"gene": "Gene", "species": "Species", "brain_region": "BrainRegion"}
FINE_LEVELS = {"supertype", "cluster", "type"}


def entity_class(row: Dict[str, str]) -> str:
    if row["entity_type"] == "cell_type":
        return "CellSubtype" if row.get("hierarchy_level") in FINE_LEVELS else "CellType"
    return CLASS_BY_TYPE.get(row["entity_type"], "ScientificNamedEntity")


def surfaces(row: Dict[str, str]) -> List[str]:
    out = [row["label_verbatim"]] + ait_tables.split_multi(row.get("aliases", ""))
    seen, res = set(), []
    for s in out:
        s = s.replace("\\|", "|").strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            res.append(s)
    return sorted(res, key=len, reverse=True)


def _pattern(surf: str, line_numbers: bool = False) -> re.Pattern:
    # "_" is a boundary, not a letter: text layers print italics as _DRD1_
    head = r"(?<![A-Za-z0-9-])" if surf[0].isalnum() else ""
    tail = r"(?![A-Za-z0-9])" if surf[-1].isalnum() else ""
    body = flex(surf)
    if line_numbers:  # a preprint's margin line number between two words ("tail of 137 caudate")
        body = body.replace(WS, WS + r"(?:\d{1,4}" + WS + ")?")
    return re.compile(head + body + tail)


def _unitalic(text: str) -> str:
    """Same length, '_' -> ' ', so expand_mentions sees _DRD1_ as a word (offsets kept)."""
    return text.replace("_", " ")


def grounded_items(row: Dict[str, str], text: str) -> List[dict]:
    """Occurrences of the row's surfaces inside its verified evidence spans."""
    starts = ait_tables.split_multi(row.get("evidence_char_start", ""))
    ends = ait_tables.split_multi(row.get("evidence_char_end", ""))
    verified = ait_tables.split_multi(row.get("evidence_verified", ""))
    items, taken = [], []
    for i, (a, b) in enumerate(zip(starts, ends)):
        if i < len(verified) and verified[i] not in ("exact", "exact_offset_corrected", "fuzzy"):
            continue
        try:
            a, b = int(a), int(b)
        except ValueError:
            continue
        for surf in surfaces(row):
            for m in _pattern(surf, line_numbers=True).finditer(text, a, b):
                if any(m.start() < y and x < m.end() for x, y in taken):
                    continue
                taken.append((m.start(), m.end()))
                items.append({"entity": text[m.start():m.end()], "start": m.start(), "end": m.end()})
    return items


def load_tables(out_dir: Path) -> Dict[str, List[Dict[str, str]]]:
    return ait_tables.load_dir(out_dir)


def build_result(data: Dict[str, List[Dict[str, str]]], text: str, *, source: Optional[Path],
                 expand_all: bool = True) -> Tuple[dict, dict, dict]:
    """(working result JSON, kg_plan, report) from the AIT tables."""
    paper = (data.get("paper.csv") or [{}])[0]
    rows = [r for r in data["entities.csv"] if not ait_tables.is_quarantined(r)]
    model = (paper.get("extractor_version") or "unknown").split("/")[-1]
    src_model = f"llm_ner:{model}"
    # identity: one key per row; a collision (two rows, one normalized label) is
    # disambiguated with the paper-side hierarchy level rather than merged
    keys: Dict[str, str] = {}
    used: Dict[str, str] = {}
    for r in rows:
        base = j2t.normalize_key(r.get("label_normalized") or r["label_verbatim"], {})
        key = base
        if key in used:
            key = f"{base}_{r.get('hierarchy_level') or r['entity_type']}"
        n = 2
        while key in used:
            key, n = f"{base}_{n}", n + 1
        used[key] = r["mention_id"]
        keys[r["mention_id"]] = key

    # which rows own which surface (lowercase): an ambiguous surface is not expanded
    owners: Dict[Tuple[str, str], set] = {}
    for r in rows:
        for s in surfaces(r):
            owners.setdefault((s.lower(), entity_class(r)), set()).add(r["mention_id"])

    explicit, entries = [], []
    for r in rows:
        cls = entity_class(r)
        extra = {"label": cls, "identity_key": keys[r["mention_id"]], "ait_mention_id": r["mention_id"],
                 "source_model": src_model, "concept_mapping_provenance": None}
        for it in grounded_items(r, text):
            explicit.append({**it, **extra})
        if expand_all:
            for s in surfaces(r):
                if len(owners[(s.lower(), cls)]) == 1:
                    entries.append({"entity": s, "label": cls})
    plain = _unitalic(text)
    items, rep = expand({"entries": entries, "items": explicit}, plain, model=model)
    for it in items:  # restore the real characters (sentence and surface) at the same offsets
        it["entity"] = text[it["start"]:it["end"]]
        sent = it.get("sentence")
        if sent:
            at = plain.rfind(sent, 0, it["end"] + len(sent))
            while at > it["start"]:
                at = plain.rfind(sent, 0, at)
            if 0 <= at <= it["start"]:
                it["sentence"] = text[at:at + len(sent)]
    by_surface = {k: next(iter(v)) for k, v in owners.items() if len(v) == 1}
    row_of = {r["mention_id"]: r for r in rows}
    out_items = []
    for it in items:
        mid = it.get("ait_mention_id") or by_surface.get((it["entity"].lower(), it["label"]))
        if not mid:
            # an expanded surface that differs only by line wrapping: match on folded text
            folded = re.sub(r"\s+", " ", it["entity"]).lower()
            mid = by_surface.get((folded, it["label"]))
        if not mid:
            continue
        it.update({"identity_key": keys[mid], "ait_mention_id": mid, "source_model": src_model,
                   # concept mapping looks up the row's normalized name, not this surface
                   # (a surface can carry a preprint margin line number or an adjective form)
                   "mapping_query": row_of[mid].get("label_normalized") or row_of[mid]["label_verbatim"]})
        it.pop("concept_mapping_provenance", None)
        out_items.append(it)
    mentioned = {it["ait_mention_id"] for it in out_items}
    missing = [r["mention_id"] for r in rows if r["mention_id"] not in mentioned]

    meta = {"paper_title": paper.get("title"), "doi": paper.get("doi"),
            "publication_date": paper.get("publication_date"), "journal": paper.get("journal"),
            "source_path": str(source) if source else None, "license": paper.get("license")}
    result = {"task_type": "ner", "ner_domain": "ait-mapping",
              "source_metadata": {k: v for k, v in meta.items() if v and v != "NA"},
              "run_metadata": {"run_id": paper.get("run_id"), "model": model},
              "entities": out_items}

    # kg_plan: names, classes, and paper-stated marker expression
    plan_entities: Dict[str, dict] = {}
    groups = mention_groups(result)
    first_gid: Dict[str, str] = {}
    sentences_of: Dict[str, List[str]] = {}
    for g in groups:
        mid = g["items"][0]["ait_mention_id"]
        r = row_of[mid]
        first_gid.setdefault(mid, g["id"])
        plan_entities[g["id"]] = {"normalized_key": keys[mid],
                                  "normalized_label": (r.get("label_normalized") or r["label_verbatim"])[:60],
                                  "class": entity_class(r)}
        sentences_of.setdefault(mid, []).extend(it.get("sentence") or "" for it in g["items"])
    gene_rows = {r["label_verbatim"].upper(): r for r in rows if r["entity_type"] == "gene"}
    n_rel, unsupported = 0, []
    for r in rows:
        if r["entity_type"] != "cell_type" or r["mention_id"] not in first_gid:
            continue
        rels = []
        for gene in ait_tables.split_multi(r.get("marker_genes_normalized") or r.get("marker_genes", "")):
            g_row = gene_rows.get(gene.upper())
            if not g_row or g_row["mention_id"] not in first_gid:
                unsupported.append(f"{r['label_verbatim']} -> {gene}: gene is not an extracted entity")
                continue
            pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(gene) + r"(?![A-Za-z0-9])")
            cell_surfs = [_pattern(s) for s in surfaces(r)]
            ev = next((s for s in sentences_of.get(r["mention_id"], []) if s and pat.search(s)), None)
            ev = ev or next((s for s in sentences_of.get(g_row["mention_id"], [])
                             if s and any(p.search(s) for p in cell_surfs)), None)
            if not ev:
                unsupported.append(f"{r['label_verbatim']} -> {gene}: no sentence names both")
                continue
            rels.append({"predicate": "expresses", "target_key": keys[g_row["mention_id"]], "evidence": ev})
        if rels:
            plan_entities[first_gid[r["mention_id"]]]["relations"] = rels
            n_rel += len(rels)
    plan = {"entities": plan_entities}
    report = {"rows": len(rows), "mentions": len(out_items), "rows_without_mentions": missing,
              "zero_hit_surfaces": rep.get("zero_hit_entries", []), "expresses_edges": n_rel,
              "markers_not_written": unsupported}
    return result, plan, report


class AitTurtleBuilder(j2t.TurtleBuilder):
    """TurtleBuilder whose cell-type mappings are the AIT edges of mappings.csv."""

    ait_edges: Dict[str, List[dict]] = {}
    ait_cards: Dict[Tuple[str, str], dict] = {}
    ait_nodes_by_tax: Dict[str, "ait_nodes.Taxonomy"] = {}
    gene_links: Dict[str, "ait_nodes.GeneMatch"] = {}

    def emit_gene(self, ent: dict, matches: List["ait_nodes.GeneMatch"]) -> bool:
        """Link a gene entity to its GeneAnnotation; False when no match resolved."""
        done = False
        for gm in matches:
            if not gm.iri:
                continue
            ref = j2t.concept_ref(gm.iri, None, self.cfg, self.registry)
            if not ref or ref[2] == "UNREGISTERED":
                self.warnings.append(f"{gm.iri} is in no registered namespace; gene link not written")
                continue
            skos = GENE_TIER_TO_SKOS[gm.tier]
            concept = self.concept_node(ref, {"ontology_label": gm.gene_symbol or gm.symbol})
            if (concept, RDFS.comment, None) not in self.g:
                self.add(concept, RDFS.comment, Literal(
                    f"GeneAnnotation {gm.gene_symbol} (trusted_ontologes/{gm.file})"))
            self.add(ent["node"], j2t.NER.resolvedToConcept, concept)
            self.add(ent["node"], j2t.MATCH_TIERS[skos], URIRef(ref[0]))
            it = {"mapping_source": "trusted", "ontology_match_type": f"gene {gm.tier}",
                  "alignment_method": f"ait_nodes gene lookup ({gm.file})"}
            self.emit_decision(ent, concept, ref, self.cfg.relation_by_tier.get(skos, "close"), it, gm.iri)
            if gm.tier != "symbol":
                dec = ent["decisions"][gm.iri][0]
                self.add(dec, RDFS.comment, Literal(
                    f"{gm.symbol!r} matched {gm.gene_symbol!r} by {gm.tier}, not exact symbol: review"))
            ent.setdefault("concept_ids", []).append(gm.iri)
            self.counts["mapped_concepts"] += 1
            self.counts["gene_links"] += 1
            done = True
        return done

    def emit_mapping(self, ent: dict):
        mids = {it.get("ait_mention_id") for grp in ent["groups"] for it in grp["items"]}
        genes = [self.gene_links[m] for m in sorted(mids) if m in self.gene_links]
        if genes:
            if self.emit_gene(ent, genes):
                return
            why = "; ".join(sorted({g.reason for g in genes if g.reason})) or "not resolved"
            self.add(ent["node"], RDFS.comment, Literal(
                f"No GeneAnnotation link ({why}); checked on {self.date}."))
            return super().emit_mapping(ent)
        edges = [e for m in mids for e in self.ait_edges.get(m, [])]
        if not edges:
            return super().emit_mapping(ent)
        emitted, gaps = 0, []
        for e in edges:
            if e.get("skos_relation") in ("", "none") or not e.get("ait_node_id"):
                gaps.append(e.get("no_match_reason") or "no defensible AIT relation")
                continue
            tax = self.ait_nodes_by_tax[e["ait_id"]]
            node = tax.node(e["ait_node_id"])
            ref = j2t.concept_ref(node.iri, None, self.cfg, self.registry)
            if not ref or ref[2] == "UNREGISTERED":
                self.warnings.append(f"{node.iri} is in no registered namespace; edge not written")
                gaps.append("AIT node namespace not registered")
                continue
            tier = e["skos_relation"].split(":", 1)[-1]
            concept = self.concept_node(ref, {"ontology_label": node.label})
            if (concept, RDFS.comment, None) not in self.g:
                self.add(concept, RDFS.comment, Literal(
                    f"{e['ait_id']} {node.level} {node.accession_id or node.label} "
                    f"(trusted_ontologes/{tax.file}; {tax.title})"))
            self.add(ent["node"], j2t.NER.resolvedToConcept, concept)
            self.add(ent["node"], j2t.MATCH_TIERS[tier], URIRef(ref[0]))
            it = {"mapping_source": "trusted", "ontology_match_type": e.get("basis_for_match", "").replace("|", ", "),
                  "alignment_method": f"ait_nodes lookup; relation by {e.get('mapped_by') or 'llm'}"}
            self.emit_decision(ent, concept, ref, self.cfg.relation_by_tier.get(tier, "close"), it, node.iri)
            dec = ent["decisions"][node.iri][0]
            for txt in (e.get("mapping_evidence"), e.get("notes")):
                if txt:
                    self.add(dec, RDFS.comment, Literal(txt))
            card = self.ait_cards.get((e["mention_id"], e["ait_node_id"]))
            if card:
                self.add(dec, RDFS.comment, Literal(
                    f"marker diff ({card.get('gene_namespace')}): shared [{card.get('genes_shared')}], "
                    f"paper-only [{card.get('genes_paper_only')}], taxonomy-only "
                    f"[{card.get('genes_taxonomy_only')}], jaccard {card.get('jaccard')}"))
            ent.setdefault("concept_ids", []).append(node.iri)
            emitted += 1
            self.counts["mapped_concepts"] += 1
            self.counts["ait_edges"] += 1
        if not emitted:
            self.add(ent["node"], RDFS.comment, Literal(
                f"No AIT taxonomy edge ({'; '.join(gaps) or 'no mapping row'}); checked on {self.date}."))
            self.counts["unmapped_entities"] += 1


def paper_species(entities: List[Dict[str, str]]) -> Tuple[str, str]:
    """(name, ncbi_taxon_id) of the paper's one experimental species, else ('', '')."""
    exp = {(r["label_verbatim"], r.get("ncbi_taxon_id", "")) for r in entities
           if r["entity_type"] == "species" and r.get("species_role") == "experimental"}
    return next(iter(exp)) if len(exp) == 1 else ("", "")


def concept_map(result: dict, text: str, skip: frozenset = frozenset()) -> dict:
    """Map the non-gene entities of the working result against the trusted ontologies.

    Flow: extraction (the tables) -> concept mapping (trusted files only) -> Turtle.
    The lexicon is built on first use (`concept_mapping index`, incremental). `skip`:
    mention ids whose mapping is an AIT edge (written from mappings.csv instead)."""
    from scripts import concept_mapping as cm
    mapper = cm.ConceptMapper(cm.load_config(), sources=["trusted"])
    rep = {"sources": ["trusted"], "mapped": {}, "unmapped": {}, "missing_files": []}
    if not mapper.usable_sources():
        rep["error"] = "no trusted ontology is indexed or present"
        return rep
    rep["missing_files"] = [s.spec["file"] for s in mapper.trusted.lexicon.missing_files()]
    items = [it for it in result["entities"]
             if it.get("label") != "Gene" and it.get("ait_mention_id") not in skip]
    sub_result = {"entities": items}
    cm.map_result(sub_result, mapper, texts=[text])
    result.setdefault("stats", {})["alignment"] = sub_result["stats"]["alignment"]
    seen = set()
    for it in items:
        key = (it.get("identity_key"), it.get("label"))
        if key in seen:
            continue
        seen.add(key)
        bucket = "mapped" if it.get("ontology_id") else "unmapped"
        rep[bucket][it["label"]] = rep[bucket].get(it["label"], 0) + 1
    return rep


def link_genes(rows: List[Dict[str, str]], default_species: Tuple[str, str] = ("", "")
               ) -> Tuple[Dict[str, "ait_nodes.GeneMatch"], dict]:
    """{mention_id: GeneMatch} for every gene row. Code only: never from memory.

    The species of a gene row is its `ncbi_taxon_id`, else its `species` name (common or
    scientific), else `default_species` (the paper's one experimental species). The
    annotation is the catalog's `gene_annotations` entry for it (ENSEMBL or NCBI
    gff2jsonld output in trusted_ontologes/). Every row ends linked or with a reason."""
    links: Dict[str, "ait_nodes.GeneMatch"] = {}
    rep = {"rows": len(rows), "linked": 0, "weaker_tier": [], "unresolved": [], "no_annotation": [],
           "species_from_paper": [], "files": {}}
    for r in rows:
        symbol = r.get("label_normalized") or r["label_verbatim"]
        name, taxon = (r.get("species") or "").strip(), (r.get("ncbi_taxon_id") or "").strip()
        if not name and not taxon:
            name, taxon = default_species
            if name or taxon:
                rep["species_from_paper"].append(symbol)
        lk = ait_nodes.gene_lookup("", taxon) if taxon else None
        lk = lk or (ait_nodes.gene_lookup(name) if name else None)
        if lk is None:
            sp = name or (f"NCBITaxon:{taxon}" if taxon else "")
            gm = ait_nodes.GeneMatch(symbol, reason=f"no trusted gene annotation for species {sp or '(none given)'!r}")
            rep["no_annotation"].append(f"{symbol} ({sp or 'no species'})")
        else:
            gm = lk.resolve(symbol)
            if gm.iri:
                rep["linked"] += 1
                rep["files"][lk.file] = rep["files"].get(lk.file, 0) + 1
                if gm.tier != "symbol":
                    rep["weaker_tier"].append(f"{symbol} -> {gm.gene_symbol} ({gm.tier})")
            else:
                rep["unresolved"].append(f"{symbol}: {gm.reason}")
        links[r["mention_id"]] = gm
    return links, rep


def convert(out_dir: Path, text_path: Path, *, source: Optional[Path] = None, out: Optional[Path] = None,
            profile: str = "compact", expand_all: bool = True, gate: bool = True) -> dict:
    issues = [i for i in ait_tables.validate(out_dir) if i.level == "error"]
    if issues:
        raise SystemExit(f"ait_tables validate reports {len(issues)} error(s); fix the tables first")
    data = load_tables(out_dir)
    text = text_path.read_text(encoding="utf-8")
    result, plan, report = build_result(data, text, source=source, expand_all=expand_all)
    ait_edged = frozenset(m["mention_id"] for m in ait_tables.current_mappings(data["mappings.csv"])
                          if m.get("ait_node_id") and m.get("skos_relation") not in ("", "none"))
    report["concept_mapping"] = concept_map(result, text, ait_edged)
    paper_id = (data.get("paper.csv") or [{}])[0].get("paper_id") or out_dir.name
    stem = re.sub(r"[^\w.-]+", "_", paper_id)
    work = out_dir / ".structsense"
    work.mkdir(exist_ok=True)
    (work / f"{stem}_ait_final.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    (work / f"{stem}_ait_kg_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))

    edges: Dict[str, List[dict]] = {}
    for m in ait_tables.current_mappings(data["mappings.csv"]):
        edges.setdefault(m["mention_id"], []).append(m)
    AitTurtleBuilder.ait_edges = edges
    AitTurtleBuilder.ait_cards = {(c["mention_id"], c["ait_node_id"]): c for c in data.get("entity_cards.csv") or []}
    AitTurtleBuilder.ait_nodes_by_tax = {}
    AitTurtleBuilder.gene_links, gene_report = link_genes(
        [r for r in data["entities.csv"] if r["entity_type"] == "gene" and not ait_tables.is_quarantined(r)],
        paper_species(data["entities.csv"]))
    report["genes"] = gene_report
    for m in data["mappings.csv"]:
        if m.get("ait_node_id") and m["ait_id"] not in AitTurtleBuilder.ait_nodes_by_tax:
            AitTurtleBuilder.ait_nodes_by_tax[m["ait_id"]] = ait_nodes.load(m["ait_id"])
    ttl, rep = j2t.result_to_ttl(result, kg_plan=plan, profile=profile, run_id=result["run_metadata"].get("run_id"),
                                 source_path=source, variant=VARIANT, builder_cls=AitTurtleBuilder,
                                 paper_slug=stem)
    out = out or out_dir / f"{stem}.ttl"
    out.write_text(ttl)
    report.update({"ttl": str(out), "triples": rep["triples"], "counts": rep["counts"],
                   "converter_warnings": rep["warnings"]})
    if gate:
        import subprocess
        p = subprocess.run([sys.executable, "-m", "scripts.validate_ttl", str(out)], cwd=_SCRIPTS.parent,
                           capture_output=True, text=True)
        report["gate_exit"] = p.returncode
        report["gate_output"] = (p.stdout + p.stderr).strip()
        if p.returncode != 0:
            bad = out.with_suffix(".invalid.ttl")
            out.rename(bad)
            report["ttl"] = str(bad)
    (work / f"{stem}_ait_ttl_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out_dir", type=Path, help="directory holding the seven AIT tables")
    ap.add_argument("--text", type=Path, required=True, help="the text file the evidence offsets index")
    ap.add_argument("--source", type=Path, help="source document (PDF), for its checksum and file name")
    ap.add_argument("--out", type=Path, help="output .ttl (default <out_dir>/<paper_id>.ttl)")
    ap.add_argument("--profile", choices=["compact", "full"], default="compact")
    ap.add_argument("--grounded-only", action="store_true",
                    help="mentions only inside verified evidence spans (no expansion)")
    ap.add_argument("--no-gate", action="store_true", help="skip validate_ttl (never for a deliverable)")
    args = ap.parse_args(argv)
    rep = convert(args.out_dir, args.text, source=args.source, out=args.out, profile=args.profile,
                  expand_all=not args.grounded_only, gate=not args.no_gate)
    c = rep["counts"]
    print(f"wrote {rep['ttl']}: {rep['triples']} triples, {c.get('entities', 0)} entities, "
          f"{c.get('mentions', 0)} mentions, {c.get('ait_edges', 0)} AIT edges, "
          f"{c.get('gene_links', 0)} gene links, {rep['expresses_edges']} expresses edges")
    cmr = rep.get("concept_mapping") or {}
    if cmr.get("error"):
        print(f"  concept mapping (trusted ontologies): {cmr['error']}")
    else:
        mapped = ", ".join(f"{k} {v}" for k, v in sorted(cmr.get("mapped", {}).items())) or "none"
        unmapped = ", ".join(f"{k} {v}" for k, v in sorted(cmr.get("unmapped", {}).items())) or "none"
        print(f"  concept mapping (trusted ontologies): mapped {mapped}; unmapped {unmapped}")
        if cmr.get("missing_files"):
            print(f"  trusted files listed in priority.md but missing: {', '.join(cmr['missing_files'])}")
    g = rep.get("genes") or {}
    if g.get("rows"):
        files = ", ".join(f"{f} ({n})" for f, n in sorted(g["files"].items())) or "none"
        print(f"  genes linked: {g['linked']}/{g['rows']} (annotation: {files})")
    for w in g.get("species_from_paper", []):
        print(f"  gene with no species, linked in the paper's experimental species: {w}")
    for w in g.get("weaker_tier", []):
        print(f"  gene linked by a weaker tier (review): {w}")
    for w in g.get("unresolved", []) + g.get("no_annotation", []):
        print(f"  gene not linked: {w}")
    for w in rep["markers_not_written"]:
        print(f"  marker not written: {w}")
    if rep["rows_without_mentions"]:
        print(f"  rows with no grounded mention: {rep['rows_without_mentions']}")
    for w in rep["converter_warnings"][:15]:
        print(f"  warning: {w}")
    if "gate_exit" in rep:
        print(rep["gate_output"].splitlines()[-1] if rep["gate_output"] else "")
        return rep["gate_exit"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
