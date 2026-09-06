"use client";

import { useState } from "react";
import type { PendingScript } from "@/lib/api";

interface ScriptReviewCardProps {
  script: PendingScript;
  busy?: boolean;
  selected?: boolean;
  onToggleSelect?: (chapterId: string) => void;
  onApprove: (chapterId: string) => void;
  onReject: (chapterId: string) => void;
  onSave: (chapterId: string, scriptText: string) => void;
}

/**
 * One chapter's script, with the approve/reject/edit actions.
 *
 * Editing is inline rather than a modal, matching CasesView — the only
 * editing precedent in this panel — instead of hand-rolling an overlay with
 * its own focus trapping and scroll locking.
 */
export default function ScriptReviewCard({
  script,
  busy = false,
  selected = false,
  onToggleSelect,
  onApprove,
  onReject,
  onSave,
}: ScriptReviewCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(script.script);

  const trimmed = draft.trim();
  const draftWords = trimmed ? trimmed.split(/\s+/).length : 0;

  function startEditing() {
    setDraft(script.script);
    setEditing(true);
  }

  return (
    <article className="case-card" data-testid={`script-card-${script.id}`}>
      <div className="doc-top">
        {onToggleSelect && (
          <input
            type="checkbox"
            checked={selected}
            aria-label={`Seleccionar ${script.title}`}
            onChange={() => onToggleSelect(script.id)}
          />
        )}
        <div className="doc-title-block">
          <h3>{script.title}</h3>
          <p className="doc-meta">{script.source_citation}</p>
        </div>
        <span className={`stamp${script.script_approved ? " approved-tag" : ""}`}>
          {script.script_approved ? "Guion aprobado" : "Guion pendiente"}
        </span>
      </div>

      {editing ? (
        <div className="preview">
          <label htmlFor={`script-text-${script.id}`}>Guion</label>
          <textarea
            id={`script-text-${script.id}`}
            className="preview-script"
            rows={10}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <p className="doc-meta">
            {draftWords} palabras · {draft.length} caracteres
          </p>
          {/* Shown unconditionally: /script/update resets approval even when
              the chapter is currently approved, so the consequence must be
              visible before saving, not discovered afterwards. */}
          <p role="note" className="doc-meta">
            Guardar reiniciará la aprobación: el guion volverá a quedar pendiente.
          </p>
          <div className="actions">
            <button
              className="btn btn-approve"
              type="button"
              disabled={busy || trimmed.length === 0}
              onClick={() => {
                onSave(script.id, draft);
                setEditing(false);
              }}
            >
              Guardar
            </button>
            <button className="btn" type="button" onClick={() => setEditing(false)}>
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="preview">
          <p className="preview-script">{script.script}</p>
          {script.visual_notes && (
            <p className="doc-hook">
              <span className="preview-tag">Indicaciones visuales</span>{" "}
              {script.visual_notes}
            </p>
          )}
          <p className="doc-meta">{script.word_count} palabras</p>
          <div className="actions">
            {!script.script_approved && (
              <button
                className="btn btn-approve"
                type="button"
                disabled={busy}
                onClick={() => onApprove(script.id)}
              >
                Aprobar guion
              </button>
            )}
            {script.script_approved && (
              <button
                className="btn"
                type="button"
                disabled={busy}
                onClick={() => onReject(script.id)}
              >
                Rechazar guion
              </button>
            )}
            <button className="btn" type="button" disabled={busy} onClick={startEditing}>
              Editar
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
