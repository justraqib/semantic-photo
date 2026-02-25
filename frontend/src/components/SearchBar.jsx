import { useEffect, useRef, useState } from 'react';

const SEARCH_HINTS = [
  'beach sunset with golden sky',
  'birthday party with cake',
  'mountain hiking trail',
  'red dress at a wedding',
  'cat sleeping on a sofa',
  'city skyline at night',
  'family dinner outdoors',
];

export default function SearchBar({ onSearch, onClear, isSearching }) {
  const [value, setValue] = useState('');
  const [placeholderText, setPlaceholderText] = useState('');
  const [hintIndex, setHintIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isFocused || value) return;

    const hint = SEARCH_HINTS[hintIndex];
    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          if (charIndex < hint.length) {
            setPlaceholderText(hint.slice(0, charIndex + 1));
            setCharIndex((prev) => prev + 1);
          } else {
            setTimeout(() => setIsDeleting(true), 1500);
          }
        } else {
          if (charIndex > 0) {
            setPlaceholderText(hint.slice(0, charIndex - 1));
            setCharIndex((prev) => prev - 1);
          } else {
            setIsDeleting(false);
            setHintIndex((prev) => (prev + 1) % SEARCH_HINTS.length);
          }
        }
      },
      isDeleting ? 30 : 60
    );

    return () => clearTimeout(timeout);
  }, [charIndex, isDeleting, hintIndex, isFocused, value]);

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
      inputRef.current?.blur();
    }
  };

  return (
    <div className="relative mb-6">
      <div
        className={`relative flex items-center rounded-2xl border transition-all duration-300 ${
          isFocused
            ? 'border-accent bg-surface shadow-lg shadow-accent/10'
            : 'border-surface-border bg-surface hover:border-foreground-dim'
        }`}
      >
        <div className="pointer-events-none pl-4">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={`transition-colors duration-200 ${isFocused ? 'text-accent-light' : 'text-foreground-dim'}`}>
            <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
            <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={isFocused ? 'Describe what you are looking for...' : placeholderText || 'Search photos...'}
          className="w-full bg-transparent px-3 py-3.5 text-foreground placeholder-foreground-dim outline-none"
        />

        {isSearching && (
          <div className="pointer-events-none pr-4">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-surface-border border-t-accent" />
          </div>
        )}

        {value && !isSearching && (
          <button
            type="button"
            onClick={() => {
              setValue('');
              onClear();
            }}
            className="mr-2 flex h-7 w-7 items-center justify-center rounded-full text-foreground-dim transition-colors hover:bg-surface-hover hover:text-foreground"
            aria-label="Clear search"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>

      {!value && !isFocused && (
        <p className="mt-2 text-center text-xs text-foreground-dim">
          Search by anything — beach sunset, red dress, birthday
        </p>
      )}
    </div>
  );
}
