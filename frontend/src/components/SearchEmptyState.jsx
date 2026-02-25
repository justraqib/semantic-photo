export default function SearchEmptyState({ query, onClear }) {
  return (
    <div className="glass-card px-6 py-16 text-center animate-fade-in">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-muted">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-accent-light">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      </div>
      <h2 className="mb-2 text-xl font-semibold text-foreground">
        {'No photos found for "' + query + '"'}
      </h2>
      <p className="mb-6 text-foreground-muted">
        Try different words — describe what you see in the photo.
      </p>
      <button
        type="button"
        onClick={onClear}
        className="btn-secondary"
      >
        Clear search
      </button>
    </div>
  );
}
