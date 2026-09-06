"use client";

import { useEffect, useRef, useState } from "react";
import { videoFileUrl, type VideoGeneration } from "@/lib/api";

export const POLL_INTERVAL_MS = 5000;
/**
 * Composition runs in-process on the backend, so a server restart mid-render
 * leaves rows PENDING forever. Polling stops after this many ticks (~5 min)
 * and hands the operator an explicit refresh instead of hammering the API
 * from an open tab indefinitely.
 */
export const MAX_POLL_ATTEMPTS = 60;

const PLATFORMS = ["tiktok", "instagram", "facebook", "x"] as const;
const LANGUAGE_LABELS: Record<string, string> = { es: "Español", en: "Inglés" };

const STATUS_LABELS: Record<VideoGeneration["status"], string> = {
  pending: "Generando…",
  generated: "Listo",
  failed: "Falló",
};

interface VideoGenerationCardProps {
  chapterId: string;
  scriptApproved: boolean;
  videos: VideoGeneration[] | null;
  busy?: boolean;
  error?: string | null;
  onGenerate: (
    chapterId: string,
    options: { platforms: string[]; languages: string[] },
  ) => void;
  onRetry: (chapterId: string, videoGenerationId: string) => void;
  /** Must be referentially stable, or the poll interval re-arms every render. */
  onPoll: (chapterId: string) => void;
}

export default function VideoGenerationCard({
  chapterId,
  scriptApproved,
  videos,
  busy = false,
  error = null,
  onGenerate,
  onRetry,
  onPoll,
}: VideoGenerationCardProps) {
  const [platforms, setPlatforms] = useState<string[]>([...PLATFORMS]);
  const [languages, setLanguages] = useState<string[]>(["es"]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [pollExhausted, setPollExhausted] = useState(false);
  const attemptsRef = useRef(0);

  const hasPending = videos?.some((video) => video.status === "pending") ?? false;
  const hasFailed = videos?.some((video) => video.status === "failed") ?? false;

  useEffect(() => {
    if (!hasPending || pollExhausted) return;

    const interval = setInterval(() => {
      attemptsRef.current += 1;
      if (attemptsRef.current >= MAX_POLL_ATTEMPTS) {
        setPollExhausted(true);
        return;
      }
      onPoll(chapterId);
    }, POLL_INTERVAL_MS);

    // Cleared on unmount, and whenever nothing is pending any more — the
    // effect simply does not re-arm.
    return () => clearInterval(interval);
  }, [hasPending, pollExhausted, chapterId, onPoll]);

  function resumePolling() {
    attemptsRef.current = 0;
    setPollExhausted(false);
    onPoll(chapterId);
  }

  function toggle(list: string[], value: string, set: (next: string[]) => void) {
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  return (
    <div className="preview open" data-testid={`videos-${chapterId}`}>
      <h4>Video</h4>
      {error && <p role="alert">{error}</p>}

      {!scriptApproved && (
        <p className="doc-meta">Aprueba el guion para poder generar el video.</p>
      )}

      <fieldset>
        <legend>Plataformas</legend>
        {PLATFORMS.map((platform) => (
          <label key={platform}>
            <input
              type="checkbox"
              checked={platforms.includes(platform)}
              onChange={() => toggle(platforms, platform, setPlatforms)}
            />
            {platform}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Idiomas</legend>
        {Object.keys(LANGUAGE_LABELS).map((lang) => (
          <label key={lang}>
            <input
              type="checkbox"
              checked={languages.includes(lang)}
              onChange={() => toggle(languages, lang, setLanguages)}
            />
            {LANGUAGE_LABELS[lang]}
          </label>
        ))}
      </fieldset>

      <button
        className="btn btn-approve"
        type="button"
        disabled={!scriptApproved || busy || platforms.length === 0 || languages.length === 0}
        onClick={() => {
          attemptsRef.current = 0;
          setPollExhausted(false);
          onGenerate(chapterId, { platforms, languages });
        }}
      >
        Generar video
      </button>

      {pollExhausted && (
        <div role="status">
          <p>
            La generación está tardando más de lo esperado. Dejamos de consultar el
            estado automáticamente.
          </p>
          <button className="btn" type="button" onClick={resumePolling}>
            Actualizar estado
          </button>
        </div>
      )}

      {videos && videos.length > 0 && (
        <ul className="source-url-list">
          {videos.map((video) => (
            <li className="source-url-row" key={video.id}>
              <span>
                {video.platform} · {LANGUAGE_LABELS[video.language] ?? video.language}
              </span>
              <span className={`status-pill ${video.status}`}>
                {STATUS_LABELS[video.status]}
              </span>

              {video.status === "generated" && (
                <>
                  {video.size_mb === null ? (
                    // Generated but the file is gone — distinct from a
                    // pending row, which never had one.
                    <span className="doc-meta">Archivo faltante en disco</span>
                  ) : (
                    <span className="doc-meta">{video.size_mb.toFixed(1)} MB</span>
                  )}
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setPreviewId(previewId === video.id ? null : video.id)}
                  >
                    {previewId === video.id ? "Ocultar" : "Ver"}
                  </button>
                  <a className="btn" href={videoFileUrl(video.id)} download>
                    Descargar
                  </a>
                </>
              )}

              {video.status === "failed" && (
                <>
                  {video.error_message && (
                    <span className="doc-meta">{video.error_message}</span>
                  )}
                  <button
                    className="btn"
                    type="button"
                    disabled={busy}
                    onClick={() => onRetry(chapterId, video.id)}
                  >
                    Reintentar
                  </button>
                </>
              )}

              {previewId === video.id && video.size_mb !== null && (
                <video
                  data-testid={`player-${video.id}`}
                  controls
                  width={320}
                  src={videoFileUrl(video.id)}
                >
                  {/* Captions are burned into the frame by FFmpeg, so there
                      is no separate track to attach here. */}
                </video>
              )}
            </li>
          ))}
        </ul>
      )}

      {hasFailed && (
        <button
          className="btn"
          type="button"
          disabled={busy}
          onClick={() => onRetry(chapterId, "")}
        >
          Reintentar todos los fallidos
        </button>
      )}
    </div>
  );
}
