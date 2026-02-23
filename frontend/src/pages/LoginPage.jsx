import { loginWithGoogle } from '../api/auth';

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="mb-2 text-center text-4xl font-bold text-slate-900">Semantic Photo</h1>
        <p className="mb-8 text-center text-slate-600">AI-powered search for your photos</p>
      <button
        onClick={loginWithGoogle}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-3 font-medium text-slate-800 hover:bg-slate-50"
      >
        <img src="https://www.google.com/favicon.ico" width={20} height={20} alt="Google" />
        Continue with Google
      </button>
        <p className="mt-5 text-center text-sm text-slate-500">
          Your photos are private and only visible to you.
        </p>
      </div>
    </div>
  );
}
