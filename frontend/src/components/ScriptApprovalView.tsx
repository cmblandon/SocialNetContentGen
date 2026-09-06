"use client";

import { useEffect, useMemo, useState } from "react";
import ScriptReviewCard from "@/components/ScriptReviewCard";
import {
  apiErrorDetail,
  approveScript,
  fetchPendingScripts,
  rejectScript,
  updateScript,
  type PendingScript,
} from "@/lib/api";

type Notice = { kind: "success" | "error"; message: string };

/**
 * The script review queue: every chapter still in play, whether or not its
 * script is approved. Bulk approval lives here rather than in the Pipeline
 * feed, which is organised per chapter.
 */
export default function ScriptApprovalView() {
  const [scripts, setScripts] = useState<PendingScript[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [busyIds, setBusyIds] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    fetchPendingScripts()
      .then((loaded) => {
        if (active) setScripts(loaded);
      })
      .catch(() => {
        if (active) setLoadError("No se pudieron cargar los guiones.");
      });
    return () => {
      active = false;
    };
  }, []);

  const visible = useMemo(() => {
    if (!scripts) return null;
    const needle = query.trim().toLowerCase();
    if (!needle) return scripts;
    return scripts.filter(
      (script) =>
        script.title.toLowerCase().includes(needle) ||
        script.source_citation.toLowerCase().includes(needle),
    );
  }, [scripts, query]);

  function replaceScript(chapterId: string, patch: Partial<PendingScript>) {
    setScripts(
      (prev) =>
        prev?.map((script) =>
          script.id === chapterId ? { ...script, ...patch } : script,
        ) ?? null,
    );
  }

  async function runAction(
    chapterId: string,
    action: () => Promise<{ script_approved: boolean; script_approved_at: string | null }>,
    patch?: Partial<PendingScript>,
  ) {
    setBusyIds((prev) => [...prev, chapterId]);
    try {
      const result = await action();
      replaceScript(chapterId, {
        ...patch,
        script_approved: result.script_approved,
        script_approved_at: result.script_approved_at,
      });
      return true;
    } catch (error) {
      // A 409 here is a real editorial conflict (e.g. a chapter with no
      // platform versions), so show what the server said rather than a
      // generic failure the operator cannot act on.
      setNotice({
        kind: "error",
        message: apiErrorDetail(error) ?? "La acción no se pudo completar.",
      });
      return false;
    } finally {
      setBusyIds((prev) => prev.filter((id) => id !== chapterId));
    }
  }

  async function handleApprove(chapterId: string) {
    if (await runAction(chapterId, () => approveScript(chapterId))) {
      setNotice({ kind: "success", message: "Guion aprobado." });
    }
  }

  async function handleReject(chapterId: string) {
    if (await runAction(chapterId, () => rejectScript(chapterId))) {
      setNotice({ kind: "success", message: "Guion rechazado." });
    }
  }

  async function handleSave(chapterId: string, scriptText: string) {
    const wordCount = scriptText.trim() ? scriptText.trim().split(/\s+/).length : 0;
    const saved = await runAction(chapterId, () => updateScript(chapterId, scriptText), {
      script: scriptText,
      word_count: wordCount,
    });
    if (saved) {
      setNotice({
        kind: "success",
        message: "Guion actualizado. La aprobación se reinició.",
      });
    }
  }

  async function handleBulkApprove() {
    const targets = selectedIds.filter(
      (id) => scripts?.find((script) => script.id === id)?.script_approved === false,
    );
    let failures = 0;
    for (const chapterId of targets) {
      if (!(await runAction(chapterId, () => approveScript(chapterId)))) failures += 1;
    }
    setSelectedIds([]);
    setNotice({
      kind: failures ? "error" : "success",
      message: failures
        ? `${targets.length - failures} de ${targets.length} guiones aprobados.`
        : `${targets.length} guiones aprobados.`,
    });
  }

  function toggleSelect(chapterId: string) {
    setSelectedIds((prev) =>
      prev.includes(chapterId)
        ? prev.filter((id) => id !== chapterId)
        : [...prev, chapterId],
    );
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Guiones</h1>
          <p>Revisa y aprueba los guiones antes de generar los videos.</p>
        </div>
      </div>

      <div className="view-card">
        {loadError && <p role="alert">{loadError}</p>}
        {notice && (
          <p role={notice.kind === "error" ? "alert" : "status"}>{notice.message}</p>
        )}

        <form className="search-form" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="script-search">Buscar</label>
          <input
            id="script-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>

        {selectedIds.length > 0 && (
          <div className="bulk-bar">
            <span className="bulk-count">{selectedIds.length} seleccionados</span>
            <div className="bulk-actions">
              <button className="btn btn-approve" type="button" onClick={handleBulkApprove}>
                Aprobar seleccionados
              </button>
              <button
                className="bulk-clear"
                type="button"
                onClick={() => setSelectedIds([])}
              >
                Limpiar
              </button>
            </div>
          </div>
        )}

        {!loadError && scripts === null && <p>Cargando guiones…</p>}
        {!loadError && visible?.length === 0 && <p>No hay guiones para revisar.</p>}

        {visible?.map((script) => (
          <ScriptReviewCard
            key={script.id}
            script={script}
            busy={busyIds.includes(script.id)}
            selected={selectedIds.includes(script.id)}
            onToggleSelect={toggleSelect}
            onApprove={handleApprove}
            onReject={handleReject}
            onSave={handleSave}
          />
        ))}
      </div>
    </>
  );
}
