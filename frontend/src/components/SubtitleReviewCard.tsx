"use client";

import { useState } from "react";
import type { SubtitleLanguage, SubtitleTrack } from "@/lib/api";

type ViewMode = "both" | SubtitleLanguage;

const LANGUAGE_LABELS: Record<SubtitleLanguage, string> = {
  es: "Español",
  en: "Inglés",
};

interface SubtitleReviewCardProps {
  chapterId: string;
  scriptApproved: boolean;
  tracks: SubtitleTrack[] | null;
  busy?: boolean;
  error?: string | null;
  onGenerate: (chapterId: string) => void;
  onSave: (
    chapterId: string,
    lang: SubtitleLanguage,
    segments: { index: number; text: string }[],
  ) => void;
}

/**
 * Bilingual subtitle review for one chapter.
 *
 * Timing is rendered read-only: it was measured from the synthesized audio,
 * and the update endpoint preserves it by construction, so exposing it as
 * editable would promise something the API will not do.
 */
export default function SubtitleReviewCard({
  chapterId,
  scriptApproved,
  tracks,
  busy = false,
  error = null,
  onGenerate,
  onSave,
}: SubtitleReviewCardProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("both");
  const [editingLang, setEditingLang] = useState<SubtitleLanguage | null>(null);
  const [draft, setDraft] = useState<Record<number, string>>({});

  const visibleTracks =
    tracks?.filter((track) => viewMode === "both" || track.lang === viewMode) ?? [];

  function startEditing(track: SubtitleTrack) {
    setEditingLang(track.lang);
    setDraft(
      Object.fromEntries(track.segments.map((segment) => [segment.index, segment.text])),
    );
  }

  const draftIsComplete = Object.values(draft).every((text) => text.trim().length > 0);

  function saveDraft(track: SubtitleTrack) {
    onSave(
      chapterId,
      track.lang,
      // Same order and count as the stored track: the API rejects any other
      // shape with a 422, because timing is matched per segment.
      track.segments.map((segment) => ({
        index: segment.index,
        text: draft[segment.index] ?? segment.text,
      })),
    );
    setEditingLang(null);
  }

  if (!tracks || tracks.length === 0) {
    return (
      <div className="preview open" data-testid={`subtitles-${chapterId}`}>
        <h4>Subtítulos</h4>
        {error && <p role="alert">{error}</p>}
        <p className="doc-meta">
          {scriptApproved
            ? "Aún no se han generado subtítulos para este capítulo."
            : "Aprueba el guion para poder generar los subtítulos."}
        </p>
        <button
          className="btn btn-approve"
          type="button"
          disabled={!scriptApproved || busy}
          title={
            scriptApproved ? undefined : "El guion debe aprobarse antes de generar subtítulos"
          }
          onClick={() => onGenerate(chapterId)}
        >
          Generar subtítulos
        </button>
      </div>
    );
  }

  return (
    <div className="preview open" data-testid={`subtitles-${chapterId}`}>
      <h4>Subtítulos</h4>
      {error && <p role="alert">{error}</p>}

      <div className="actions" role="group" aria-label="Idioma de subtítulos">
        {(["both", "es", "en"] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            className={`btn${viewMode === mode ? " btn-approve" : ""}`}
            aria-pressed={viewMode === mode}
            onClick={() => setViewMode(mode)}
          >
            {mode === "both" ? "Ambos" : LANGUAGE_LABELS[mode]}
          </button>
        ))}
      </div>

      <div className="subtitle-grid">
        {visibleTracks.map((track) => (
          <section key={track.lang} aria-label={`Subtítulos en ${LANGUAGE_LABELS[track.lang]}`}>
            <h5>
              {LANGUAGE_LABELS[track.lang]}
              {track.edited && <span className="preview-tag">Editado</span>}
            </h5>

            {editingLang === track.lang ? (
              <>
                {track.segments.map((segment) => (
                  <div key={segment.index}>
                    <label htmlFor={`seg-${chapterId}-${track.lang}-${segment.index}`}>
                      <span className="mono">
                        {segment.start} → {segment.end}
                      </span>
                    </label>
                    <input
                      id={`seg-${chapterId}-${track.lang}-${segment.index}`}
                      value={draft[segment.index] ?? ""}
                      onChange={(event) =>
                        setDraft((prev) => ({ ...prev, [segment.index]: event.target.value }))
                      }
                    />
                  </div>
                ))}
                <p className="doc-meta">
                  Los tiempos no se modifican: se midieron sobre el audio narrado.
                </p>
                <div className="actions">
                  <button
                    className="btn btn-approve"
                    type="button"
                    disabled={busy || !draftIsComplete}
                    onClick={() => saveDraft(track)}
                  >
                    Guardar {LANGUAGE_LABELS[track.lang]}
                  </button>
                  <button className="btn" type="button" onClick={() => setEditingLang(null)}>
                    Cancelar
                  </button>
                </div>
              </>
            ) : (
              <>
                <ol>
                  {track.segments.map((segment) => (
                    <li key={segment.index}>
                      <span className="mono">
                        {segment.start} → {segment.end}
                      </span>{" "}
                      {segment.text}
                    </li>
                  ))}
                </ol>
                <button
                  className="btn"
                  type="button"
                  disabled={busy}
                  onClick={() => startEditing(track)}
                >
                  Editar {LANGUAGE_LABELS[track.lang]}
                </button>
              </>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
