import { loginWithGoogle } from '../api/auth';

export default function LoginPage() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      height: '100vh', gap: '24px', fontFamily: 'Arial'
    }}>
      <h1 style={{ fontSize: '2.5rem', color: '#1A1A2E' }}>📸 Semantic Photo</h1>
      <p style={{ color: '#555', fontSize: '1.1rem' }}>
        AI-powered search for your photos
      </p>
      <button
        onClick={loginWithGoogle}
        style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '12px 24px', fontSize: '1rem',
          border: '1px solid #ddd', borderRadius: '8px',
          cursor: 'pointer', background: 'white',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}
      >
        <img src="https://www.google.com/favicon.ico" width={20} height={20} alt="Google" />
        Continue with Google
      </button>
    </div>
  );
}