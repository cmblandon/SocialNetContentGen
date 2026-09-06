"use client";

import type { VideoStats } from "@/lib/api";

/** Warn when free space drops below this fraction of the disk. */
const LOW_DISK_RATIO = 0.1;

export default function StorageUsageBar({ stats }: { stats: VideoStats }) {
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
