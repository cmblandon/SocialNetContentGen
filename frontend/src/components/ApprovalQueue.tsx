"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approvePlatformVersion,
  fetchPendingChapters,
  rejectPlatformVersion,
  type ApproveResponse,
  type PendingChapter,
} from "@/lib/api";

const PLATFORM_LABELS: Record<string, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  x: "X",
  facebook: "Facebook",
};

type Decision =
  | { kind: "approved"; outcome: ApproveResponse["publish_outcome"] }
  | { kind: "rejected" };

export default function ApprovalQueue() {
  const [chapters, setChapters] = useState<PendingChapter[] | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setChapters(await fetchPendingChapters());
    } catch {
      setError("Failed to load the approval queue.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApprove(platformVersionId: string) {
    const response = await approvePlatformVersion(platformVersionId);
    setDecisions((prev) => ({
      ...prev,
      [platformVersionId]: { kind: "approved", outcome: response.publish_outcome },
    }));
  }

  async function handleReject(platformVersionId: string) {
    await rejectPlatformVersion(platformVersionId);
    setDecisions((prev) => ({ ...prev, [platformVersionId]: { kind: "rejected" } }));
  }

  if (error) return <p role="alert">{error}</p>;
  if (chapters === null) return <p>Loading approval queue…</p>;
  if (chapters.length === 0) return <p>Nothing pending approval.</p>;

  return (
    <ul>
      {chapters.map((chapter) => (
        <li key={chapter.id}>
          <article>
            <h2>{chapter.document.title}</h2>
            <p>
              {chapter.document.agency} — {chapter.document.doc_type}
              {chapter.document.published_date ? ` — ${chapter.document.published_date}` : ""}
            </p>
            <p>{chapter.story_summary}</p>

            <h3>{chapter.title}</h3>
            <p>{chapter.script}</p>
            <p>Source: {chapter.source_citation}</p>

            <ul>
              {chapter.platform_versions.map((pv) => {
                const label = PLATFORM_LABELS[pv.platform] ?? pv.platform;
                const decision = decisions[pv.id];
                return (
                  <li key={pv.id}>
                    <h4>{label}</h4>
                    <p>{pv.content}</p>
                    {!decision && (
                      <>
                        <button onClick={() => handleApprove(pv.id)}>Approve {label}</button>
                        <button onClick={() => handleReject(pv.id)}>Reject {label}</button>
                      </>
                    )}
                    {decision?.kind === "rejected" && <p>Rejected.</p>}
                    {decision?.kind === "approved" &&
                      (() => {
                        const outcome = decision.outcome;
                        return (
                          <p>
                            {outcome.published
                              ? `Published (post id: ${outcome.external_post_id})`
                              : outcome.proposed_time
                                ? `Proposed schedule: ${outcome.proposed_time}, pending approval`
                                : `Publish failed: ${outcome.error_message}`}
                          </p>
                        );
                      })()}
                  </li>
                );
              })}
            </ul>
          </article>
        </li>
      ))}
    </ul>
  );
}
