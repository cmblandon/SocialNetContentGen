"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ScriptReviewCard from "@/components/ScriptReviewCard";
import SubtitleReviewCard from "@/components/SubtitleReviewCard";
import VideoGenerationCard from "@/components/VideoGenerationCard";
import {
  apiErrorDetail,
  approvePlatformVersion,
  approveScript,
  fetchCheckpointSummary,
  fetchPendingChapters,
  fetchPendingScripts,
  fetchSourceUrls,
  fetchChapterVideos,
  fetchSubtitles,
  generateSubtitles,
  generateVideo,
  publishPlatformVersion,
  rejectScript,
  resumePipeline,
  retryVideo,
  runResearch,
  updateScript,
  updateSubtitleTrack,
  type CheckpointSummary,
  type PendingChapter,
  type PendingScript,
  type PlatformVersionSummary,
  type SubtitleLanguage,
  type SubtitleTrack,
  type VideoGeneration,
} from "@/lib/api";

const NETWORKS = [
  { key: "tiktok", label: "TikTok" },
  { key: "instagram", label: "Instagram" },
  { key: "facebook", label: "Facebook" },
  { key: "x", label: "X" },
] as const;

type RunStatus = "idle" | "running" | "done" | "error";

function isCaseApproved(chapter: PendingChapter): boolean {
  return chapter.platform_versions.every((pv) => pv.status !== "pending_review");
}

function parseHashtags(content: string): string[] {
  try {
    const parsed = JSON.parse(content);
    return Array.isArray(parsed.hashtags) ? parsed.hashtags : [];
  } catch {
    return [];
  }
}

function withUpdatedPlatformVersion(
  chapters: PendingChapter[],
  chapterId: string,
  platformVersionId: string,
  status: string
): PendingChapter[] {
  return chapters.map((chapter) =>
    chapter.id !== chapterId
      ? chapter
      : {
          ...chapter,
          platform_versions: chapter.platform_versions.map((pv) =>
            pv.id === platformVersionId ? { ...pv, status } : pv
          ),
        }
  );
}

function withToggled<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export default function PipelineFeed() {
  const [chapters, setChapters] = useState<PendingChapter[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sourceUrls, setSourceUrls] = useState<string[] | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [checkpointSummary, setCheckpointSummary] = useState<CheckpointSummary | null>(null);
  const [scriptsById, setScriptsById] = useState<Record<string, PendingScript>>({});
  const [subtitlesById, setSubtitlesById] = useState<Record<string, SubtitleTrack[]>>({});
  const [subtitleErrors, setSubtitleErrors] = useState<Record<string, string>>({});
  const [busyChapterIds, setBusyChapterIds] = useState<string[]>([]);
  const [videosById, setVideosById] = useState<Record<string, VideoGeneration[]>>({});
  const [videoErrors, setVideoErrors] = useState<Record<string, string>>({});

  const loadChapters = useCallback(async () => {
    try {
      setChapters(await fetchPendingChapters());
    } catch {
      setError("Failed to load the pipeline feed.");
    }
  }, []);

  const loadScripts = useCallback(async () => {
    try {
      const loaded = await fetchPendingScripts();
      setScriptsById(Object.fromEntries(loaded.map((script) => [script.id, script])));
    } catch {
      // The feed is still usable without the script layer; leaving it empty
      // simply hides the review section rather than blanking the whole page.
    }
  }, []);

  const loadCheckpointSummary = useCallback(async () => {
    try {
      setCheckpointSummary(await fetchCheckpointSummary());
    } catch {
      setCheckpointSummary({ pending: 0, failed: 0 });
    }
  }, []);

  useEffect(() => {
    loadChapters();
    loadScripts();
    loadCheckpointSummary();
    fetchSourceUrls()
      .then(setSourceUrls)
      .catch(() => setSourceUrls([]));
  }, [loadChapters, loadScripts, loadCheckpointSummary]);

  const selectedApprovedChapters = useMemo(
    () => (chapters ?? []).filter((c) => selectedIds.has(c.id) && isCaseApproved(c)),
    [chapters, selectedIds]
  );

  async function handleRunPipeline() {
    if (!sourceUrls || sourceUrls.length === 0) return;
    setRunStatus("running");
    try {
      const trimmedQuery = query.trim();
      if (trimmedQuery) {
        await runResearch(sourceUrls, trimmedQuery);
      } else {
        await runResearch(sourceUrls);
      }
      setRunStatus("done");
      await loadChapters();
    } catch {
      setRunStatus("error");
    }
  }

  async function handleResumePipeline() {
    await resumePipeline();
    await loadChapters();
    await loadCheckpointSummary();
  }

  function markBusy(chapterId: string, busy: boolean) {
    setBusyChapterIds((prev) =>
      busy ? [...prev, chapterId] : prev.filter((id) => id !== chapterId),
    );
  }

  function patchScript(chapterId: string, patch: Partial<PendingScript>) {
    setScriptsById((prev) =>
      prev[chapterId] ? { ...prev, [chapterId]: { ...prev[chapterId], ...patch } } : prev,
    );
  }

  async function handleScriptApprove(chapterId: string) {
    markBusy(chapterId, true);
    try {
      const result = await approveScript(chapterId);
      patchScript(chapterId, {
        script_approved: result.script_approved,
        script_approved_at: result.script_approved_at,
      });
    } catch (caught) {
      setError(apiErrorDetail(caught) ?? "No se pudo aprobar el guion.");
    } finally {
      markBusy(chapterId, false);
    }
  }

  async function handleScriptReject(chapterId: string) {
    markBusy(chapterId, true);
    try {
      const result = await rejectScript(chapterId);
      patchScript(chapterId, {
        script_approved: result.script_approved,
        script_approved_at: result.script_approved_at,
      });
    } catch (caught) {
      setError(apiErrorDetail(caught) ?? "No se pudo rechazar el guion.");
    } finally {
      markBusy(chapterId, false);
    }
  }

  async function handleScriptSave(chapterId: string, scriptText: string) {
    markBusy(chapterId, true);
    try {
      const result = await updateScript(chapterId, scriptText);
      const trimmed = scriptText.trim();
      patchScript(chapterId, {
        script: scriptText,
        word_count: trimmed ? trimmed.split(/\s+/).length : 0,
        script_approved: result.script_approved,
        script_approved_at: result.script_approved_at,
      });
    } catch (caught) {
      setError(apiErrorDetail(caught) ?? "No se pudo guardar el guion.");
    } finally {
      markBusy(chapterId, false);
    }
  }

  async function loadSubtitles(chapterId: string) {
    // Lazy: fetching every chapter's subtitles on page load would be one
    // request per chapter for a section most of them never open.
    if (subtitlesById[chapterId]) return;
    try {
      const loaded = await fetchSubtitles(chapterId);
      setSubtitlesById((prev) => ({ ...prev, [chapterId]: loaded }));
    } catch (caught) {
      setSubtitleErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudieron cargar los subtítulos.",
      }));
    }
  }

  async function handleSubtitleGenerate(chapterId: string) {
    markBusy(chapterId, true);
    setSubtitleErrors((prev) => {
      const next = { ...prev };
      delete next[chapterId];
      return next;
    });
    try {
      const generated = await generateSubtitles(chapterId);
      setSubtitlesById((prev) => ({ ...prev, [chapterId]: generated }));
    } catch (caught) {
      setSubtitleErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudieron generar los subtítulos.",
      }));
    } finally {
      markBusy(chapterId, false);
    }
  }

  async function handleSubtitleSave(
    chapterId: string,
    lang: SubtitleLanguage,
    segments: { index: number; text: string }[],
  ) {
    markBusy(chapterId, true);
    try {
      const updated = await updateSubtitleTrack(chapterId, lang, segments);
      setSubtitlesById((prev) => ({
        ...prev,
        [chapterId]: (prev[chapterId] ?? []).map((track) =>
          track.lang === lang ? updated : track,
        ),
      }));
    } catch (caught) {
      setSubtitleErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudieron guardar los subtítulos.",
      }));
    } finally {
      markBusy(chapterId, false);
    }
  }

  const loadVideos = useCallback(async (chapterId: string) => {
    try {
      const loaded = await fetchChapterVideos(chapterId);
      setVideosById((prev) => ({ ...prev, [chapterId]: loaded }));
    } catch (caught) {
      setVideoErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudo consultar el estado del video.",
      }));
    }
  }, []);

  async function handleVideoGenerate(
    chapterId: string,
    options: { platforms: string[]; languages: string[] },
  ) {
    markBusy(chapterId, true);
    setVideoErrors((prev) => {
      const next = { ...prev };
      delete next[chapterId];
      return next;
    });
    try {
      const created = await generateVideo(chapterId, options);
      // The 202 carries the pending rows, so the card shows "generating"
      // immediately instead of waiting for the first poll five seconds later.
      setVideosById((prev) => ({
        ...prev,
        [chapterId]: [...(prev[chapterId] ?? []), ...created],
      }));
    } catch (caught) {
      setVideoErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudo generar el video.",
      }));
    } finally {
      markBusy(chapterId, false);
    }
  }

  async function handleVideoRetry(chapterId: string, videoGenerationId: string) {
    markBusy(chapterId, true);
    try {
      await retryVideo(chapterId, videoGenerationId || undefined);
      await loadVideos(chapterId);
    } catch (caught) {
      setVideoErrors((prev) => ({
        ...prev,
        [chapterId]: apiErrorDetail(caught) ?? "No se pudo reintentar la generación.",
      }));
    } finally {
      markBusy(chapterId, false);
    }
  }

  function togglePreview(chapterId: string) {
    setExpandedIds((prev) => withToggled(prev, chapterId));
  }

  function toggleSelected(chapterId: string) {
    setSelectedIds((prev) => withToggled(prev, chapterId));
  }

  async function handleApproveCase(chapter: PendingChapter) {
    const pendingIds = chapter.platform_versions
      .filter((pv) => pv.status === "pending_review")
      .map((pv) => pv.id);
    await Promise.all(pendingIds.map((id) => approvePlatformVersion(id)));
    setChapters((prev) =>
      prev
        ? prev.map((c) =>
            c.id !== chapter.id
              ? c
              : {
                  ...c,
                  platform_versions: c.platform_versions.map((pv) =>
                    pendingIds.includes(pv.id) ? { ...pv, status: "approved" } : pv
                  ),
                }
          )
        : prev
    );
  }

  async function handlePublish(chapterId: string, platformVersionId: string) {
    const outcome = await publishPlatformVersion(platformVersionId);
    const status = outcome.published ? "published" : outcome.error_message ? "failed" : "approved";
    setChapters((prev) =>
      prev ? withUpdatedPlatformVersion(prev, chapterId, platformVersionId, status) : prev
    );
  }

  async function handleBulkPublish(networkKey: string) {
    const targets = selectedApprovedChapters.flatMap((chapter) =>
      chapter.platform_versions
        .filter((pv) => pv.platform === networkKey && pv.status === "approved")
        .map((pv) => ({ chapterId: chapter.id, platformVersionId: pv.id }))
    );
    await Promise.allSettled(
      targets.map((t) => handlePublish(t.chapterId, t.platformVersionId))
    );
  }

  const eligibleBulkNetworks = NETWORKS.filter((network) =>
    selectedApprovedChapters.some((chapter) =>
      chapter.platform_versions.some((pv) => pv.platform === network.key && pv.status === "approved")
    )
  );

  if (error) return <p role="alert">{error}</p>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Pipeline de contenido</h1>
          <p>Revisa lo que encontró el sistema, aprueba y publica.</p>
        </div>
        <div className="run-cluster">
          <div className="query-field">
            <label htmlFor="research-query">Tema (opcional)</label>
            <input
              id="research-query"
              placeholder="Ej. incidentes de radar en Malmstrom"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <span className={`status-pill${runStatus === "running" ? " working" : runStatus === "done" ? " done" : runStatus === "error" ? " error" : ""}`}>
            {runStatus === "running"
              ? "Ejecutando pipeline…"
              : runStatus === "done"
                ? "Listo"
                : runStatus === "error"
                  ? "Error al ejecutar"
                  : "Inactivo"}
          </span>
          <button
            className="btn-run"
            onClick={handleRunPipeline}
            disabled={!sourceUrls || sourceUrls.length === 0 || runStatus === "running"}
            title={sourceUrls && sourceUrls.length === 0 ? "Configura al menos una fuente en Configuración" : undefined}
          >
            Ejecutar pipeline
          </button>
        </div>
      </div>

      {checkpointSummary && (checkpointSummary.pending > 0 || checkpointSummary.failed > 0) && (
        <div className="checkpoint-banner" data-testid="checkpoint-banner">
          <span className="checkpoint-banner-text">
            {checkpointSummary.pending} documento(s) pendiente(s) de curación
            {checkpointSummary.failed > 0 && `, ${checkpointSummary.failed} fallido(s)`}
          </span>
          <button className="btn-resume" onClick={handleResumePipeline}>
            Reanudar pipeline
          </button>
        </div>
      )}

      <div className="bulk-bar" data-testid="bulk-bar">
        <span className={`bulk-count${selectedApprovedChapters.length > 0 ? " active" : ""}`}>
          {selectedApprovedChapters.length === 0
            ? "Selecciona casos aprobados para publicar en lote"
            : `${selectedApprovedChapters.length} caso(s) seleccionado(s)`}
        </span>
        <div className="bulk-actions">
          {eligibleBulkNetworks.map((network) => (
            <button
              key={network.key}
              className="net-btn"
              onClick={() => handleBulkPublish(network.key)}
            >
              Publicar en {network.label}
            </button>
          ))}
        </div>
        {selectedIds.size > 0 && (
          <button className="bulk-clear" onClick={() => setSelectedIds(new Set())}>
            Limpiar selección
          </button>
        )}
      </div>

      <div className="feed">
        {chapters === null && <p>Cargando pipeline…</p>}
        {chapters !== null && chapters.length === 0 && <p>No hay casos en el pipeline.</p>}
        {chapters?.map((chapter) => {
          const approved = isCaseApproved(chapter);
          const tiktokVersion = chapter.platform_versions.find((pv) => pv.platform === "tiktok");
          const hashtags = tiktokVersion ? parseHashtags(tiktokVersion.content) : [];
          const previewOpen = expandedIds.has(chapter.id);
          const script = scriptsById[chapter.id];
          const chapterBusy = busyChapterIds.includes(chapter.id);

          return (
            <article className="case-card" key={chapter.id}>
              <div className="doc-face">
                <div className="doc-top">
                  <div className="doc-title-block">
                    <h3>{chapter.document.title}</h3>
                    <p className="doc-hook">{chapter.story_summary}</p>
                  </div>
                  <span className={`stamp ${approved ? "approved" : "pending"}`}>
                    {approved ? "Aprobado" : "Pendiente"}
                  </span>
                </div>
                <div className="doc-meta">
                  <span>
                    <b>Procedencia:</b> {chapter.document.agency}
                  </span>
                  <span>
                    <b>Tipo:</b> {chapter.document.doc_type}
                  </span>
                  <span>
                    <b>Fecha:</b> {chapter.document.published_date ?? "—"}
                  </span>
                  <span>
                    <b>Capítulo:</b> {chapter.title}
                  </span>
                </div>
              </div>

              <div className="actions">
                <label className={`select-toggle${approved ? "" : " disabled"}`}>
                  <input
                    type="checkbox"
                    aria-label="Seleccionar"
                    disabled={!approved}
                    checked={selectedIds.has(chapter.id)}
                    onChange={() => toggleSelected(chapter.id)}
                  />
                  <span>Seleccionar</span>
                </label>
                <button
                  className="btn btn-preview"
                  onClick={() => {
                    if (!previewOpen) {
                      loadSubtitles(chapter.id);
                      loadVideos(chapter.id);
                    }
                    togglePreview(chapter.id);
                  }}
                >
                  {previewOpen ? "Ocultar guion" : "Vista previa"}
                </button>
                {approved ? (
                  <span className="approved-tag">Aprobado</span>
                ) : (
                  <button className="btn btn-approve" onClick={() => handleApproveCase(chapter)}>
                    Aprobar
                  </button>
                )}
              </div>

              {previewOpen && (
                <>
                  <div className="preview open">
                    <h4>Guion — {chapter.title}</h4>
                    <p className="preview-script">{chapter.script}</p>
                    <div>
                      {hashtags.map((tag) => (
                        <span className="preview-tag" key={tag}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {script && (
                    <ScriptReviewCard
                      script={script}
                      busy={chapterBusy}
                      onApprove={handleScriptApprove}
                      onReject={handleScriptReject}
                      onSave={handleScriptSave}
                    />
                  )}

                  {/* Subtitles only make sense once the narration text is
                      settled; the endpoint refuses with 409 otherwise. */}
                  {script?.script_approved && (
                    <SubtitleReviewCard
                      chapterId={chapter.id}
                      scriptApproved
                      tracks={subtitlesById[chapter.id] ?? null}
                      busy={chapterBusy}
                      error={subtitleErrors[chapter.id] ?? null}
                      onGenerate={handleSubtitleGenerate}
                      onSave={handleSubtitleSave}
                    />
                  )}

                  {script?.script_approved && (
                    <VideoGenerationCard
                      chapterId={chapter.id}
                      scriptApproved
                      videos={videosById[chapter.id] ?? null}
                      busy={chapterBusy}
                      error={videoErrors[chapter.id] ?? null}
                      onGenerate={handleVideoGenerate}
                      onRetry={handleVideoRetry}
                      onPoll={loadVideos}
                    />
                  )}
                </>
              )}

              <div className="net-status-row">
                {NETWORKS.map((network) => {
                  const pv = chapter.platform_versions.find(
                    (candidate: PlatformVersionSummary) => candidate.platform === network.key
                  );
                  if (!pv) return null;

                  if (pv.status === "published") {
                    return (
                      <span className="net-chip done" key={network.key} title={`${network.label} — publicado`}>
                        <span className="mono">{network.label[0]}</span>
                      </span>
                    );
                  }

                  if (pv.status === "approved") {
                    return (
                      <button
                        key={network.key}
                        className="net-btn"
                        onClick={() => handlePublish(chapter.id, pv.id)}
                      >
                        Publicar en {network.label}
                      </button>
                    );
                  }

                  return (
                    <span className="net-chip" key={network.key} title={`${network.label} — ${pv.status}`}>
                      <span className="mono">{network.label[0]}</span>
                    </span>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
