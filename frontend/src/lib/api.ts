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

/**
 * Carries the HTTP status alongside the message.
 *
 * The video endpoints distinguish 409 (a real editorial conflict worth
 * explaining — script not approved, video already exists, nothing failed to
 * retry) from everything else, which a string-only Error cannot express
 * without parsing the message back apart.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(
      `${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

/** Detail string FastAPI puts in `{"detail": "..."}`, for user-facing copy. */
export function apiErrorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const match = error.message.match(/\{"detail":\s*"((?:[^"\\]|\\.)*)"\}/);
  if (!match) return null;
  try {
    return JSON.parse(`"${match[1]}"`) as string;
  } catch {
    return match[1];
  }
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

// --- Script review (video-generation-pipeline, phase 11) --------------------

export interface PendingScript {
  id: string;
  title: string;
  script: string;
  visual_notes: string | null;
  source_citation: string;
  script_approved: boolean;
  script_approved_at: string | null;
  created_at: string;
  word_count: number;
}

export interface ScriptActionResult {
  chapter_id: string;
  script_approved: boolean;
  script_approved_at: string | null;
  /** How many of the chapter's platform versions the decision was written to. */
  platform_versions_updated: number;
}

export function fetchPendingScripts(): Promise<PendingScript[]> {
  return request<PendingScript[]>("/chapters/pending/scripts");
}

export function approveScript(chapterId: string): Promise<ScriptActionResult> {
  return request<ScriptActionResult>(`/chapters/${chapterId}/script/approve`, {
    method: "POST",
  });
}

export function rejectScript(chapterId: string): Promise<ScriptActionResult> {
  return request<ScriptActionResult>(`/chapters/${chapterId}/script/reject`, {
    method: "POST",
  });
}

/** Always resets `script_approved` to false, including on an approved chapter. */
export function updateScript(chapterId: string, scriptText: string): Promise<ScriptActionResult> {
  return request<ScriptActionResult>(`/chapters/${chapterId}/script/update`, {
    method: "POST",
    body: JSON.stringify({ script_text: scriptText }),
  });
}

// --- Subtitles (phase 12) ---------------------------------------------------

export type SubtitleLanguage = "es" | "en";

export interface SubtitleSegment {
  index: number;
  /** SRT timecode, e.g. "00:00:04,000". Not editable. */
  start: string;
  end: string;
  text: string;
}

export interface SubtitleTrack {
  lang: SubtitleLanguage;
  edited: boolean;
  updated_at: string | null;
  segments: SubtitleSegment[];
}

export function generateSubtitles(chapterId: string): Promise<SubtitleTrack[]> {
  return request<SubtitleTrack[]>(`/chapters/${chapterId}/subtitles/generate`, {
    method: "POST",
  });
}

export function fetchSubtitles(chapterId: string): Promise<SubtitleTrack[]> {
  return request<SubtitleTrack[]>(`/chapters/${chapterId}/subtitles`);
}

/** Timing is preserved server-side; only text may change, and the segment
 * count must match the stored track exactly. */
export function updateSubtitleTrack(
  chapterId: string,
  lang: SubtitleLanguage,
  segments: { index: number; text: string }[],
): Promise<SubtitleTrack> {
  return request<SubtitleTrack>(`/chapters/${chapterId}/subtitles/update`, {
    method: "POST",
    body: JSON.stringify({ lang, segments }),
  });
}

// --- Video generation (phase 13) --------------------------------------------

export type VideoStatus = "pending" | "generated" | "failed";

export interface VideoGeneration {
  id: string;
  platform_version_id: string;
  platform: string;
  language: string;
  status: VideoStatus;
  video_file_path: string | null;
  subtitle_file_path: string | null;
  error_message: string | null;
  retry_of_id: string | null;
  created_at: string;
  generated_at: string | null;
  /** Null when never generated OR when the file is missing from disk. */
  size_mb: number | null;
}

export function generateVideo(
  chapterId: string,
  options?: { platforms?: string[]; languages?: string[] },
): Promise<VideoGeneration[]> {
  return request<VideoGeneration[]>(`/chapters/${chapterId}/video/generate`, {
    method: "POST",
    body: JSON.stringify(options ?? {}),
  });
}

export function fetchChapterVideos(chapterId: string): Promise<VideoGeneration[]> {
  return request<VideoGeneration[]>(`/chapters/${chapterId}/video`);
}

export function retryVideo(
  chapterId: string,
  videoGenerationId?: string,
): Promise<VideoGeneration[]> {
  return request<VideoGeneration[]>(`/chapters/${chapterId}/video/retry`, {
    method: "POST",
    body: JSON.stringify(videoGenerationId ? { video_generation_id: videoGenerationId } : {}),
  });
}

// --- Video library (phase 14) -----------------------------------------------

export interface LibraryVideo extends VideoGeneration {
  chapter_id: string;
  chapter_title: string;
}

/** Deliberately NOT a LibraryVideo: /videos/stats returns a narrower row with
 * no chapter_title and no status. */
export interface LargestVideo {
  id: string;
  chapter_id: string;
  platform: string;
  language: string;
  size_mb: number;
  video_file_path: string;
}

export interface VideoStats {
  total_storage_mb: number;
  count_by_status: Record<VideoStatus, number>;
  largest_videos: LargestVideo[];
  /** Rows marked generated whose file is gone from disk. */
  missing_on_disk: number;
  /** Null when capacity could not be read — do not render as 0. */
  disk_free_mb: number | null;
  disk_total_mb: number | null;
}

export interface VideoMetrics {
  total_attempts: number;
  generated: number;
  failed: number;
  pending: number;
  /** Null when nothing has an outcome yet — not 0, which would read as total failure. */
  success_rate: number | null;
  average_composition_seconds: number | null;
  failures_by_step: Record<string, number>;
  /** A proxy for third-party API usage, not a quota reading. */
  generations_last_24h: number;
}

export interface DeleteVideoResult {
  video_generation_id: string;
  video_file_deleted: boolean;
  subtitle_file_deleted: boolean;
  video_file_retained_reason: string | null;
  subtitle_file_retained_reason: string | null;
}

/** Only `status` is filtered server-side; platform/language/date are client-side. */
export function fetchVideoLibrary(status?: VideoStatus): Promise<LibraryVideo[]> {
  return request<LibraryVideo[]>(`/videos${status ? `?status=${status}` : ""}`);
}

export function fetchVideoStats(): Promise<VideoStats> {
  return request<VideoStats>("/videos/stats");
}

export function fetchVideoMetrics(): Promise<VideoMetrics> {
  return request<VideoMetrics>("/videos/metrics");
}

export function deleteVideo(id: string): Promise<DeleteVideoResult> {
  return request<DeleteVideoResult>(`/videos/${id}`, { method: "DELETE" });
}

/** URL the browser can actually play or download; `video_file_path` is a
 * server-side filesystem path and is not reachable from here. */
export function videoFileUrl(id: string): string {
  return `${API_BASE_URL}/videos/${id}/file`;
}
