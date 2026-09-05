# `src/core/` — Ingestion Pipeline Domain

Pure domain layer for the ingestion pipeline ("Proyecto Expediente"): no
imports from `src/infrastructure/`, no external libraries beyond the
standard library and `typing`.

- `entities.py` — `FichaEstructurada`, the canonical dataclass produced by
  depurating a document.
- `ports.py` — `typing.Protocol` contracts (`IPdfInspector`, `IOcrProcessor`,
  `IDocumentTextLoader`, `ILLMClient`, `IDocumentRepository`,
  `ISemanticIndex`) that `src/infrastructure/` implements and
  `src/application/` consumes.

For the full pipeline data flow, project structure, and setup instructions,
see the root [`README.md`](../../README.md). For the editorial service
built on top of this pipeline (`src/editorial/`), see that same file's
"Editorial Service" section and `docs/data-model.md`.
