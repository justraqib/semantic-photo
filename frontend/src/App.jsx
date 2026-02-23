import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { useAuth } from './hooks/useAuth';
import AuthSuccess from './pages/AuthSuccess';
import Albums from './pages/Albums';
import AlbumDetail from './pages/AlbumDetail';
import Gallery from './pages/Gallery';
import LoginPage from './pages/LoginPage';
import MapPage from './pages/Map';
import Settings from './pages/Settings';

function ProtectedRoute() {
  const { isLoggedIn, isLoading } = useAuth();
  if (isLoading) return null;
  return isLoggedIn ? <Outlet /> : <Navigate to="/login" replace />;
}

function ProtectedLayout() {
  return (
    <div className="min-h-screen bg-slate-100">
      <Navbar />
      <Outlet />
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
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/albums" element={<Albums />} />
            <Route path="/albums/:albumId" element={<AlbumDetail />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/gallery" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
