"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approvePlatformVersion,
  fetchPendingChapters,
  fetchSourceUrls,
  publishPlatformVersion,
  runResearch,
  type PendingChapter,
  type PlatformVersionSummary,
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

  const loadChapters = useCallback(async () => {
    try {
      setChapters(await fetchPendingChapters());
    } catch {
      setError("Failed to load the pipeline feed.");
    }
  }, []);

  useEffect(() => {
    loadChapters();
    fetchSourceUrls()
      .then(setSourceUrls)
      .catch(() => setSourceUrls([]));
  }, [loadChapters]);

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
                <button className="btn btn-preview" onClick={() => togglePreview(chapter.id)}>
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
