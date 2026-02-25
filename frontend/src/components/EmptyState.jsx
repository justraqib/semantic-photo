export default function EmptyState({ message = 'Upload your first photo to get started' }) {
  return (
    <div className="glass-card border-dashed px-6 py-16 text-center animate-fade-in">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-muted">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      </div>
      <p className="text-lg font-medium text-foreground">No photos yet</p>
      <p className="mt-2 text-sm text-foreground-muted">{message}</p>
    </div>
  );
}
