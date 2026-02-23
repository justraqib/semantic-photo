export default function EmptyState({ message = 'Upload your first photo to get started' }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center text-slate-600">
      <p className="text-lg font-medium">No photos yet</p>
      <p className="mt-2 text-sm">{message}</p>
    </div>
  );
}
