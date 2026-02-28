import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteDuplicatePhotos, listDuplicateGroups } from '../api/photos';

const DELETE_ALL_CHUNK_SIZE = 40;

function ProgressRing({ value }) {
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const safeValue = Math.max(0, Math.min(100, value));
  const offset = circumference * (1 - safeValue / 100);

  return (
    <div className="relative h-28 w-28">
      <svg className="h-28 w-28 -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={radius} stroke="currentColor" strokeWidth="8" className="text-surface-light" fill="none" />
        <circle
          cx="60"
          cy="60"
          r={radius}
          stroke="currentColor"
          strokeWidth="8"
          className="text-accent-light transition-all duration-300"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-lg font-semibold text-foreground">
        {Math.round(safeValue)}%
      </div>
    </div>
  );
}

export default function DuplicatesPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmDeleteAllOpen, setConfirmDeleteAllOpen] = useState(false);
  const [deleteAllProgress, setDeleteAllProgress] = useState({
    isRunning: false,
    total: 0,
    deleted: 0,
    processed: 0,
    failed: 0,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['duplicate-groups'],
    queryFn: async () => (await listDuplicateGroups()).data,
  });

  const groups = data?.groups || [];
  const totalDuplicates = data?.total_duplicates || 0;

  const deleteMutation = useMutation({
    mutationFn: deleteDuplicatePhotos,
    onSuccess: () => {
      setSelected(new Set());
      setConfirmOpen(false);
      queryClient.invalidateQueries({ queryKey: ['duplicate-groups'] });
      queryClient.invalidateQueries({ queryKey: ['photos'] });
    },
  });
  const deleteAllMutation = useMutation({
    mutationFn: async () => {
      const candidateIds = groups.flatMap((group) => group.photos.slice(1).map((photo) => photo.id));
      const total = candidateIds.length;
      if (total === 0) {
        setDeleteAllProgress({
          isRunning: false,
          total: 0,
          deleted: 0,
          processed: 0,
          failed: 0,
        });
        return { deleted: 0, total: 0, failed: 0 };
      }

      setDeleteAllProgress({
        isRunning: true,
        total,
        deleted: 0,
        processed: 0,
        failed: 0,
      });

      let deleted = 0;
      let processed = 0;
      let failed = 0;

      for (let index = 0; index < candidateIds.length; index += DELETE_ALL_CHUNK_SIZE) {
        const chunk = candidateIds.slice(index, index + DELETE_ALL_CHUNK_SIZE);
        try {
          const response = await deleteDuplicatePhotos({ photo_ids: chunk });
          const chunkDeleted = Number(response?.data?.deleted || 0);
          deleted += chunkDeleted;
          processed += chunk.length;
          failed += Math.max(0, chunk.length - chunkDeleted);
        } catch {
          processed += chunk.length;
          failed += chunk.length;
        }

        setDeleteAllProgress({
          isRunning: true,
          total,
          deleted,
          processed,
          failed,
        });
      }

      return { deleted, total, failed };
    },
    onSuccess: () => {
      setSelected(new Set());
      setConfirmDeleteAllOpen(false);
      setDeleteAllProgress((prev) => ({
        ...prev,
        isRunning: false,
      }));
      queryClient.invalidateQueries({ queryKey: ['duplicate-groups'] });
      queryClient.invalidateQueries({ queryKey: ['photos'] });
    },
    onError: () => {
      setDeleteAllProgress((prev) => ({
        ...prev,
        isRunning: false,
      }));
    },
  });

  const selectedCount = selected.size;
  const selectedIds = useMemo(() => Array.from(selected), [selected]);
  const deleteAllPercent =
    deleteAllProgress.total > 0
      ? (deleteAllProgress.processed / deleteAllProgress.total) * 100
      : 0;

  const toggle = (photoId) => {
    const next = new Set(selected);
    if (next.has(photoId)) next.delete(photoId);
    else next.add(photoId);
    setSelected(next);
  };

  return (
    <div className="mx-auto max-w-[1400px] p-4 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Duplicates</h1>
          <p className="text-sm text-foreground-muted">
            {totalDuplicates} duplicates detected.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          disabled={selectedCount === 0}
          onClick={() => setConfirmOpen(true)}
        >
          Delete selected ({selectedCount})
        </button>
      </div>
      <div className="mb-5">
        <button
          type="button"
          className="btn-secondary"
          disabled={groups.length === 0 || deleteAllMutation.isPending}
          onClick={() => setConfirmDeleteAllOpen(true)}
        >
          {deleteAllMutation.isPending ? 'Deleting all...' : 'Delete all duplicates (one click)'}
        </button>
      </div>

      {deleteAllProgress.isRunning && (
        <div className="mb-6 rounded-2xl border border-surface-border bg-surface p-4">
          <div className="flex flex-col items-center gap-3 md:flex-row md:gap-5">
            <ProgressRing value={deleteAllPercent} />
            <div className="text-center md:text-left">
              <p className="text-sm font-semibold text-foreground">Deleting duplicate photos in background</p>
              <p className="mt-1 text-sm text-foreground-muted">
                Total {deleteAllProgress.total} · Processed {deleteAllProgress.processed} · Deleted {deleteAllProgress.deleted} · Failed {deleteAllProgress.failed}
              </p>
            </div>
          </div>
        </div>
      )}

      {isLoading && <p className="text-sm text-foreground-muted">Loading duplicates...</p>}
      {!isLoading && groups.length === 0 && (
        <p className="text-sm text-foreground-muted">No duplicates found.</p>
      )}

      <div className="space-y-6">
        {groups.map((group) => (
          <div key={group.phash} className="rounded-2xl border border-surface-border bg-surface p-4">
            <p className="mb-3 text-xs text-foreground-muted">Hash: {group.phash} · {group.count} photos</p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
              {group.photos.map((photo) => (
                <label key={photo.id} className="relative block cursor-pointer">
                  <img src={photo.thumbnail_url} alt="" className="h-28 w-full rounded-lg object-cover" />
                  <input
                    type="checkbox"
                    checked={selected.has(photo.id)}
                    onChange={() => toggle(photo.id)}
                    className="absolute left-2 top-2 h-4 w-4"
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-surface-border bg-background p-5">
            <h2 className="mb-2 text-lg font-semibold text-foreground">Delete selected duplicates?</h2>
            <p className="mb-4 text-sm text-foreground-muted">
              This will permanently delete {selectedCount} selected photos.
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setConfirmOpen(false)}>Cancel</button>
              <button
                type="button"
                className="btn-primary bg-danger hover:bg-danger/90"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate({ photo_ids: selectedIds })}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDeleteAllOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-surface-border bg-background p-5">
            <h2 className="mb-2 text-lg font-semibold text-foreground">Delete all duplicate copies?</h2>
            <p className="mb-4 text-sm text-foreground-muted">
              Keeps one photo per duplicate group and deletes the rest permanently.
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setConfirmDeleteAllOpen(false)}>Cancel</button>
              <button
                type="button"
                className="btn-primary bg-danger hover:bg-danger/90"
                disabled={deleteAllMutation.isPending}
                onClick={() => deleteAllMutation.mutate()}
              >
                {deleteAllMutation.isPending ? 'Deleting...' : 'Confirm Delete All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
