import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { useAuth } from './hooks/useAuth';
import AuthSuccess from './pages/AuthSuccess';
import Albums from './pages/Albums';
import AlbumDetail from './pages/AlbumDetail';
import Gallery from './pages/Gallery';
import Home from './pages/Home';
import LoginPage from './pages/LoginPage';
import MapPage from './pages/Map';
import PeoplePage from './pages/People';
import DuplicatesPage from './pages/Duplicates';
import Settings from './pages/Settings';

function ProtectedRoute() {
  const { isLoggedIn, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-surface-border border-t-accent" />
          <span className="text-sm text-foreground-muted">Loading...</span>
        </div>
      </div>
    );
  }
  return isLoggedIn ? <Outlet /> : <Navigate to="/login" replace />;
}

function ProtectedLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="animate-fade-in">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/success" element={<AuthSuccess />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<ProtectedLayout />}>
            <Route path="/home" element={<Home />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/people" element={<PeoplePage />} />
            <Route path="/duplicates" element={<DuplicatesPage />} />
            <Route path="/albums" element={<Albums />} />
            <Route path="/albums/:albumId" element={<AlbumDetail />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/home" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
