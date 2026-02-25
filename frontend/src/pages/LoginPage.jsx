import { useEffect, useState } from 'react';
import { loginWithGithub, loginWithGoogle } from '../api/auth';

function AnimatedLogo() {
  return (
    <div className="relative mx-auto mb-6 flex h-20 w-20 items-center justify-center">
      <div className="absolute inset-0 animate-pulse-slow rounded-2xl bg-accent/20 blur-xl" />
      <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-accent/10 border border-accent/30">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" className="text-accent-light">
          <rect x="4" y="4" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2" />
          <rect x="22" y="4" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2" />
          <rect x="4" y="22" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2" />
          <circle cx="29" cy="29" r="7" stroke="currentColor" strokeWidth="2" />
          <circle cx="29" cy="29" r="3" fill="currentColor" />
        </svg>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M18.17 8.37H10v3.41h4.59c-.39 2.06-2.13 3.22-4.59 3.22a5 5 0 010-10 4.72 4.72 0 013.3 1.28l2.55-2.55A8.16 8.16 0 0010 1.67a8.33 8.33 0 100 16.66c4.59 0 8.5-3.22 8.5-8.33a8.6 8.6 0 00-.33-1.63z" fill="#4285F4"/>
      <path d="M2.63 5.85l2.96 2.17A5 5 0 0110 5a4.72 4.72 0 013.3 1.28l2.55-2.55A8.16 8.16 0 0010 1.67 8.31 8.31 0 002.63 5.85z" fill="#EA4335"/>
      <path d="M10 18.33a8.12 8.12 0 005.74-2.22l-2.78-2.22A4.9 4.9 0 0110 15a5 5 0 01-4.69-3.24l-2.93 2.26A8.32 8.32 0 0010 18.33z" fill="#34A853"/>
      <path d="M18.17 8.37H10v3.41h4.59a4.93 4.93 0 01-1.72 2.35l2.78 2.22c1.97-1.82 3.18-4.53 3.18-7.55a8.6 8.6 0 00-.33-1.63 .38.38 0 00-.33.2z" fill="#FBBC05"/>
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.58 7.58 0 0 1 8 4.76c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

export default function LoginPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6">
      {/* Background gradient orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-80 w-80 rounded-full bg-accent/8 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-accent/5 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 h-60 w-60 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/3 blur-3xl" />
      </div>

      {/* Grid overlay */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      <div
        className={`relative w-full max-w-md transition-all duration-700 ${
          mounted ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
        }`}
      >
        <div className="glass-card p-8">
          <AnimatedLogo />

          <h1 className="mb-2 text-center text-3xl font-bold text-foreground text-balance">
            Semantic Photo
          </h1>
          <p className="mb-8 text-center text-foreground-muted">
            AI-powered search for your photos
          </p>

          <div className="flex flex-col gap-3">
            <button
              onClick={loginWithGoogle}
              className="flex w-full items-center justify-center gap-3 rounded-xl border border-surface-border bg-surface px-4 py-3.5 font-medium text-foreground transition-all duration-200 hover:border-foreground-dim hover:bg-surface-hover active:scale-[0.98]"
            >
              <GoogleIcon />
              Continue with Google
            </button>

            <button
              onClick={loginWithGithub}
              className="flex w-full items-center justify-center gap-3 rounded-xl bg-white px-4 py-3.5 font-medium text-black transition-all duration-200 hover:bg-white/90 active:scale-[0.98]"
            >
              <GitHubIcon />
              Continue with GitHub
            </button>
          </div>

          <p className="mt-6 text-center text-sm text-foreground-dim">
            Your photos are private and only visible to you.
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-foreground-dim">
          Self-hosted &middot; Open source &middot; Privacy first
        </p>
      </div>
    </div>
  );
}
