"use client";

import { useEffect, useState } from "react";
import { addSourceUrl, fetchSourceUrls, removeSourceUrl } from "@/lib/api";

export default function SourceUrlManager() {
  const [urls, setUrls] = useState<string[] | null>(null);
  const [newUrl, setNewUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSourceUrls()
      .then(setUrls)
      .catch(() => setError("Failed to load the configured source URLs."));
  }, []);

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!newUrl.trim()) return;
    const updated = await addSourceUrl(newUrl.trim());
    setUrls(updated);
    setNewUrl("");
  }

  async function handleRemove(url: string) {
    const updated = await removeSourceUrl(url);
    setUrls(updated);
  }

  if (error) return <p role="alert">{error}</p>;

  return (
    <div className="view-card">
      <form className="settings-form" onSubmit={handleAdd}>
        <label htmlFor="source-url">URL</label>
        <input
          id="source-url"
          value={newUrl}
          onChange={(e) => setNewUrl(e.target.value)}
        />
        <button type="submit">Agregar</button>
      </form>

      {urls === null && <p>Cargando fuentes…</p>}
      {urls?.length === 0 && <p>No hay fuentes configuradas.</p>}

      {urls && urls.length > 0 && (
        <ul className="source-url-list">
          {urls.map((url) => (
            <li className="source-url-row" key={url}>
              <span>{url}</span>
              <button className="btn" onClick={() => handleRemove(url)}>
                Eliminar
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
