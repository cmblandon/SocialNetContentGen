"use client";

import { useEffect, useState } from "react";
import { fetchCases, updateCaseReason, type CaseEntry } from "@/lib/api";

export default function CasesView() {
  const [cases, setCases] = useState<CaseEntry[] | null>(null);
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftReason, setDraftReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load(searchQuery?: string) {
    try {
      setCases(await fetchCases(searchQuery || undefined));
    } catch {
      setError("Failed to load covered cases.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startEditing(caseEntry: CaseEntry) {
    setEditingId(caseEntry.id);
    setDraftReason(caseEntry.reason);
  }

  async function saveEdit(id: string) {
    const updated = await updateCaseReason(id, draftReason);
    setCases((prev) => prev?.map((c) => (c.id === id ? updated : c)) ?? null);
    setEditingId(null);
  }

  if (error) return <p role="alert">{error}</p>;

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load(query);
        }}
      >
        <label htmlFor="case-search">Search</label>
        <input
          id="case-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      {cases === null && <p>Loading covered cases…</p>}
      {cases?.length === 0 && <p>No covered cases found.</p>}

      <ul>
        {cases?.map((caseEntry) => (
          <li key={caseEntry.id}>
            <p>{caseEntry.date}</p>
            <p>{caseEntry.identifier}</p>
            <p>{caseEntry.outcome}</p>
            {editingId === caseEntry.id ? (
              <>
                <label htmlFor={`reason-${caseEntry.id}`}>Reason</label>
                <textarea
                  id={`reason-${caseEntry.id}`}
                  value={draftReason}
                  onChange={(e) => setDraftReason(e.target.value)}
                />
                <button onClick={() => saveEdit(caseEntry.id)}>Save</button>
                <button onClick={() => setEditingId(null)}>Cancel</button>
              </>
            ) : (
              <>
                <p>{caseEntry.reason}</p>
                <button onClick={() => startEditing(caseEntry)}>Edit</button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
