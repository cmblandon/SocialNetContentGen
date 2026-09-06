"use client";

import type { VideoMetrics, VideoStats } from "@/lib/api";

/** Warn when free space drops below this fraction of the disk. */
const LOW_DISK_RATIO = 0.1;
/** Each generation costs roughly one TTS synthesis and one image query, so
 * this many in a day is worth flagging before a quota is hit. */
const HIGH_DAILY_VOLUME = 50;
/** Below this, something is systematically wrong rather than flaky. */
const LOW_SUCCESS_RATE = 0.8;

export default function StorageUsageBar({
  stats,
  metrics = null,
}: {
  stats: VideoStats;
  metrics?: VideoMetrics | null;
}) {
  const capacityKnown = stats.disk_free_mb !== null && stats.disk_total_mb !== null;
  const lowDisk =
    capacityKnown && stats.disk_free_mb! / stats.disk_total_mb! < LOW_DISK_RATIO;

  return (
    <div className="storage-bar">
      <p>
        <b>Almacenamiento usado por videos:</b> {stats.total_storage_mb.toFixed(1)} MB
      </p>
      <p>
        <b>Videos:</b> {stats.count_by_status.generated} listos ·{" "}
        {stats.count_by_status.pending} generando · {stats.count_by_status.failed} fallidos
      </p>

      {capacityKnown ? (
        <p role={lowDisk ? "alert" : undefined}>
          <b>Espacio libre en disco:</b> {(stats.disk_free_mb! / 1024).toFixed(1)} GB de{" "}
          {(stats.disk_total_mb! / 1024).toFixed(1)} GB
          {lowDisk && " — queda poco espacio para generar más videos."}
        </p>
      ) : (
        // Never rendered as 0: unknown capacity must not read as a full disk.
        <p>
          <b>Espacio libre en disco:</b> desconocido
        </p>
      )}

      {metrics && metrics.total_attempts > 0 && (
        <p>
          <b>Generaciones:</b> {metrics.generated} exitosas de{" "}
          {metrics.generated + metrics.failed}
          {metrics.average_composition_seconds !== null &&
            ` · ${metrics.average_composition_seconds.toFixed(0)}s por video en promedio`}
        </p>
      )}

      {metrics &&
        metrics.success_rate !== null &&
        metrics.success_rate < LOW_SUCCESS_RATE && (
          <p role="alert">
            Solo {Math.round(metrics.success_rate * 100)}% de las generaciones
            terminan bien. Revisa los errores en el historial.
          </p>
        )}

      {metrics && metrics.generations_last_24h >= HIGH_DAILY_VOLUME && (
        <p role="alert">
          {metrics.generations_last_24h} generaciones en las últimas 24 horas.
          Cada una consume narración e imagen: revisa tu cuota de ElevenLabs.
        </p>
      )}

      {stats.missing_on_disk > 0 && (
        // Kept separate from the status counts: these rows say "generated"
        // but their file is gone, which is a different problem from a failure.
        <p role="alert">
          {stats.missing_on_disk} video(s) marcados como listos no tienen archivo en disco.
        </p>
      )}
    </div>
  );
}
