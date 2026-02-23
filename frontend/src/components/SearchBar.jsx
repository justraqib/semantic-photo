import { useEffect, useState } from 'react';

export default function SearchBar({ onSearch, onClear, isSearching }) {
  const [value, setValue] = useState('');

  useEffect(() => {
    if (value === '') {
      onClear();
    }
  }, [onClear, value]);

  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      onSearch(value.trim());
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      setValue('');
      onClear();
    }
  };

  return (
    <div className="relative mb-5">
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search photos..."
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 pr-12 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
      />
      {isSearching && (
        <div className="pointer-events-none absolute inset-y-0 right-4 flex items-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
        </div>
      )}
    </div>
  );
}
