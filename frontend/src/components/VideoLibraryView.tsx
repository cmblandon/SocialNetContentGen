"use client";

import { useEffect, useMemo, useState } from "react";
import StorageUsageBar from "@/components/StorageUsageBar";
import {
  apiErrorDetail,
  deleteVideo,
  fetchVideoLibrary,
  fetchVideoMetrics,
  fetchVideoStats,
  videoFileUrl,
  type LibraryVideo,
  type VideoMetrics,
  type VideoStats,
  type VideoStatus,
} from "@/lib/api";

const STATUS_LABELS: Record<VideoStatus, string> = {
  pending: "Generando…",
  generated: "Listo",
  failed: "Falló",
};

interface Filters {
  platform: string;
  language: string;
  status: string;
  from: string;
  to: string;
}

const EMPTY_FILTERS: Filters = { platform: "", language: "", status: "", from: "", to: "" };

export default function VideoLibraryView() {
  const [videos, setVideos] = useState<LibraryVideo[] | null>(null);
  const [stats, setStats] = useState<VideoStats | null>(null);
  const [metrics, setMetrics] = useState<VideoMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);

  useEffect(() => {
    let active = true;
    Promise.all([fetchVideoLibrary(), fetchVideoStats()])
      .then(([library, loadedStats]) => {
        if (!active) return;
        setVideos(library);
        setStats(loadedStats);
      })
      .catch(() => {
        if (active) setError("No se pudo cargar la videoteca.");
      });

    // Fetched separately and allowed to fail: metrics are supplementary, and
    // folding them into the load above would blank the whole library when
    // only the health panel is unavailable.
    fetchVideoMetrics()
      .then((loadedMetrics) => {
        if (active) setMetrics(loadedMetrics);
      })
      .catch(() => {
        if (active) setMetrics(null);
      });
    return () => {
      active = false;
    };
  }, []);

  // Only `status` is filtered server-side, so the rest happen here rather
  // than issuing a request per filter change.
  const visible = useMemo(() => {
    if (!videos) return null;
    return videos.filter((row) => {
      if (filters.platform && row.platform !== filters.platform) return false;
      if (filters.language && row.language !== filters.language) return false;
      if (filters.status && row.status !== filters.status) return false;
      const created = row.created_at.slice(0, 10);
      if (filters.from && created < filters.from) return false;
      if (filters.to && created > filters.to) return false;
      return true;
    });
  }, [videos, filters]);

  const downloadable = useMemo(
    () => (visible ?? []).filter((row) => row.status === "generated" && row.size_mb !== null),
    [visible],
  );

  async function handleDelete(row: LibraryVideo) {
    if (!window.confirm(`¿Eliminar el video de ${row.chapter_title} (${row.platform})?`)) {
      return;
    }
    try {
      const outcome = await deleteVideo(row.id);
      setVideos((prev) => prev?.filter((candidate) => candidate.id !== row.id) ?? null);
      setStats(await fetchVideoStats());

      // A retained file is not a silent no-op: say which one and why, since
      // the row disappears either way.
      const retained = [
        outcome.video_file_retained_reason && `video (${outcome.video_file_retained_reason})`,
        outcome.subtitle_file_retained_reason &&
          `subtítulos (${outcome.subtitle_file_retained_reason})`,
      ].filter(Boolean);
      setNotice(
        retained.length
          ? `Registro eliminado. Se conservó: ${retained.join("; ")}.`
          : "Video eliminado.",
      );
    } catch (caught) {
      setError(apiErrorDetail(caught) ?? "No se pudo eliminar el video.");
    }
  }

  function handleDownloadAll() {
    // Sequential anchor clicks rather than a zip: there is no archive
    // endpoint, and each file is already individually downloadable.
    for (const row of downloadable) {
      const anchor = document.createElement("a");
      anchor.href = videoFileUrl(row.id);
      anchor.download = "";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    }
    setNotice(`Descargando ${downloadable.length} video(s).`);
  }

  function setFilter(key: keyof Filters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Videos</h1>
          <p>Revisa, descarga y administra los videos generados.</p>
        </div>
      </div>

      <div className="view-card">
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}

        {stats && <StorageUsageBar stats={stats} metrics={metrics} />}

        <form className="search-form" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="filter-platform">Plataforma</label>
          <select
            id="filter-platform"
            value={filters.platform}
            onChange={(event) => setFilter("platform", event.target.value)}
          >
            <option value="">Todas</option>
            {["tiktok", "instagram", "facebook", "x"].map((platform) => (
              <option key={platform} value={platform}>
                {platform}
              </option>
            ))}
          </select>

          <label htmlFor="filter-language">Idioma</label>
          <select
            id="filter-language"
            value={filters.language}
            onChange={(event) => setFilter("language", event.target.value)}
          >
            <option value="">Todos</option>
            <option value="es">Español</option>
            <option value="en">Inglés</option>
          </select>

          <label htmlFor="filter-status">Estado</label>
          <select
            id="filter-status"
            value={filters.status}
            onChange={(event) => setFilter("status", event.target.value)}
          >
            <option value="">Todos</option>
            <option value="generated">Listo</option>
            <option value="pending">Generando</option>
            <option value="failed">Falló</option>
          </select>

          <label htmlFor="filter-from">Desde</label>
          <input
            id="filter-from"
            type="date"
            value={filters.from}
            onChange={(event) => setFilter("from", event.target.value)}
          />

          <label htmlFor="filter-to">Hasta</label>
          <input
            id="filter-to"
            type="date"
            value={filters.to}
            onChange={(event) => setFilter("to", event.target.value)}
          />
        </form>

        <button
          className="btn"
          type="button"
          disabled={downloadable.length === 0}
          onClick={handleDownloadAll}
        >
          Descargar todos ({downloadable.length})
        </button>

        {!error && videos === null && <p>Cargando videoteca…</p>}
        {!error && visible?.length === 0 && <p>No hay videos que coincidan.</p>}

        {visible && visible.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Capítulo</th>
                <th>Plataforma</th>
                <th>Idioma</th>
                <th>Estado</th>
                <th>Tamaño</th>
                <th>Generado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.id}>
                  <td>{row.chapter_title}</td>
                  <td>{row.platform}</td>
                  <td>{row.language}</td>
                  <td>{STATUS_LABELS[row.status]}</td>
                  <td>
                    {row.status === "generated" && row.size_mb === null
                      ? "Archivo faltante"
                      : row.size_mb !== null
                        ? `${row.size_mb.toFixed(1)} MB`
                        : "—"}
                  </td>
                  <td>{row.generated_at?.slice(0, 10) ?? "—"}</td>
                  <td>
                    {row.status === "generated" && row.size_mb !== null && (
                      <a className="btn" href={videoFileUrl(row.id)} download>
                        Descargar
                      </a>
                    )}
                    <button
                      className="btn"
                      type="button"
                      onClick={() => handleDelete(row)}
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
