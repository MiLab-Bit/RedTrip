# Ark evaluation integration gate — 2026-11-22

Source packages: task 37698, frore 90664; vugh 90663; xyst 90665. This is an integration worklist, NOT evidence of code integration.

## Candidate adoption
1. Import frore's negative regression tests as red tests against the untouched main baseline; preserve original failures and root-cause grouping.
2. Compare vugh and xyst fixes per issue: entity identity, aliases, city boundaries, historical evidence provenance, event ownership, geometry, walking budget and frontend contracts.
3. Port only fixes that make red tests green without discarding legitimate matches. Keep a traceable test→defect→patch→regression map.

## Release gates
- No substring-only entity attachment or fabricated coordinates; uncertain evidence must remain uncertain.
- Distinguish semantic accuracy from historical narrative coverage: a sparse but correct narrative is preferable to fabricated facts.
- Revalidate real upstream SLC/maps/LLM and browser E2E separately; offline fixture green does not imply production readiness.
- Preserve frozen-baseline failure evidence, test data and source attribution.

Status: review pending; no candidate code has been cherry-picked or merged.
