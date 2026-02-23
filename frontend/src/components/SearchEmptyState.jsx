export default function SearchEmptyState({ query, onClear }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-6 py-12 text-center">
      <div className="mb-4 text-5xl">🔎</div>
      <h2 className="mb-2 text-2xl font-semibold text-slate-900">
        No photos found for "{query}"
      </h2>
      <p className="mb-6 text-slate-600">
        Try different words — describe what you see in the photo.
      </p>
      <button
        type="button"
        onClick={onClear}
        className="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-100"
      >
        Clear search
      </button>
    </div>
  );
}
