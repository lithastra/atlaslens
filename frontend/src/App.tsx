import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import OverviewPage from './pages/OverviewPage';
import ProductivityPage from './pages/ProductivityPage';
import SecurityPage from './pages/SecurityPage';
import TimelinePage from './pages/TimelinePage';
import WorkItemsPage from './pages/WorkItemsPage';
import ReportsPage from './pages/ReportsPage';
import HealthPage from './pages/HealthPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="productivity" element={<ProductivityPage />} />
        <Route path="security" element={<SecurityPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="workitems" element={<WorkItemsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="health" element={<HealthPage />} />
      </Route>
    </Routes>
  );
}
