"use client";

import { useEffect, useState } from "react";
import { fetchPublishRecords, type PublishRecord } from "@/lib/api";

export default function Calendar() {
  const [records, setRecords] = useState<PublishRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPublishRecords()
      .then(setRecords)
      .catch(() => setError("Failed to load the editorial calendar."));
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (records === null) return <p>Loading calendar…</p>;
  if (records.length === 0) return <p>Nothing published or scheduled yet.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Network</th>
          <th>Scheduled at</th>
          <th>Status</th>
          <th>Post ID</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody>
        {records.map((record) => (
          <tr key={record.id}>
            <td>{record.platform}</td>
            <td>{record.scheduled_at ?? "—"}</td>
            <td>{record.status}</td>
            <td>{record.external_post_id ?? "—"}</td>
            <td>{record.error_message ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
