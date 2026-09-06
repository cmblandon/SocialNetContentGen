// Thin client for the editorial FastAPI service. Kept dependency-free
// (plain fetch) since this is a small internal panel — see
// docs/frontend-standards.md.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface DocumentSummary {
  id: string;
  title: string;
  agency: string;
  doc_type: string;
  published_date: string | null;
  source_url: string | null;
}

export interface PlatformVersionSummary {
  id: string;
  platform: "tiktok" | "instagram" | "x" | "facebook";
  content: string;
  status: string;
}

export interface PendingChapter {
  id: string;
  title: string;
  script: string;
  visual_notes: string | null;
  source_citation: string;
  story_summary: string;
  document: DocumentSummary;
  platform_versions: PlatformVersionSummary[];
}

export interface PublishOutcome {
  published: boolean;
  external_post_id: string | null;
  error_message: string | null;
  proposed_time: string | null;
}

export interface ApproveResponse {
  id: string;
  status: string;
}

export interface PublishRecord {
  id: string;
  platform_version_id: string;
  platform: string;
  status: string;
  external_post_id: string | null;
  scheduled_at: string | null;
  published_at: string | null;
  error_message: string | null;
}

export interface ResearchRunResult {
  documents_reviewed: number;
  stories_created: number;
  chapters_generated: number;
  pending_approval_platform_version_ids: string[];
  discarded_document_ids: string[];
}

export interface CaseEntry {
  id: string;
  date: string;
  identifier: string;
  outcome: string;
  reason: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export function fetchPendingChapters(): Promise<PendingChapter[]> {
  return request<PendingChapter[]>("/chapters/pending");
}

export function approvePlatformVersion(id: string): Promise<ApproveResponse> {
  return request<ApproveResponse>(`/platform-versions/${id}/approve`, { method: "POST" });
}

export function rejectPlatformVersion(id: string): Promise<{ id: string; status: string }> {
  return request(`/platform-versions/${id}/reject`, { method: "POST" });
}

export function publishPlatformVersion(id: string): Promise<PublishOutcome> {
  return request<PublishOutcome>(`/platform-versions/${id}/publish`, { method: "POST" });
}

export function fetchPublishRecords(): Promise<PublishRecord[]> {
  return request<PublishRecord[]>("/publish-records");
}

export function runResearch(sourceUrls: string[], query?: string): Promise<ResearchRunResult> {
  const body: { source_urls: string[]; query?: string } = { source_urls: sourceUrls };
  const trimmedQuery = query?.trim();
  if (trimmedQuery) {
    body.query = trimmedQuery;
  }
  return request<ResearchRunResult>("/research/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchSourceUrls(): Promise<string[]> {
  const { source_urls } = await request<{ source_urls: string[] }>("/research/sources");
  return source_urls;
}

export async function addSourceUrl(url: string): Promise<string[]> {
  const { source_urls } = await request<{ source_urls: string[] }>("/research/sources", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  return source_urls;
}

export async function removeSourceUrl(url: string): Promise<string[]> {
  const { source_urls } = await request<{ source_urls: string[] }>("/research/sources/delete", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  return source_urls;
}

export interface CheckpointSummary {
  pending: number;
  failed: number;
}

export function fetchCheckpointSummary(): Promise<CheckpointSummary> {
  return request<CheckpointSummary>("/research/checkpoints/summary");
}

export function resumePipeline(): Promise<ResearchRunResult> {
  return request<ResearchRunResult>("/research/resume", { method: "POST" });
}

export function fetchCases(query?: string): Promise<CaseEntry[]> {
  const search = query ? `?q=${encodeURIComponent(query)}` : "";
  return request<CaseEntry[]>(`/cases${search}`);
}

export function updateCaseReason(id: string, reason: string): Promise<CaseEntry> {
  return request<CaseEntry>(`/cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ reason }),
  });
}
