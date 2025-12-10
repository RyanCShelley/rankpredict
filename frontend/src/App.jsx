import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import StrategyDashboard from './pages/StrategyDashboard';
import OutlineBuilder from './pages/OutlineBuilder';
import AdminPanel from './pages/AdminPanel';
import Login from './pages/Login';

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" />;
};

const Navigation = () => {
  const { logout, user } = useAuth();

  return (
    <nav className="bg-white shadow-sm">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-xl font-bold text-[#223540]">
              RankPredict v2
            </Link>
            <div className="flex space-x-4">
              <Link
                to="/"
                className="text-gray-700 hover:text-[#223540] px-3 py-2 rounded-md text-sm font-medium"
              >
                Strategy Dashboard
              </Link>
              <Link
                to="/outline"
                className="text-gray-700 hover:text-[#223540] px-3 py-2 rounded-md text-sm font-medium"
              >
                Outline Builder
              </Link>
              {(user?.role === 'master' || user?.role === 'admin') && (
                <Link
                  to="/admin"
                  className="text-gray-700 hover:text-[#223540] px-3 py-2 rounded-md text-sm font-medium"
                >
                  Admin
                </Link>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">
              {user?.email}
              {user?.role === 'master' && <span className="ml-2 text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">Master</span>}
              {user?.role === 'admin' && <span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Admin</span>}
            </span>
            <button
              onClick={logout}
              className="text-gray-700 hover:text-[#223540] px-3 py-2 rounded-md text-sm font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <div className="min-h-screen bg-gray-50">
                  <Navigation />
                  <main>
                    <Routes>
                      <Route path="/" element={<StrategyDashboard />} />
                      <Route path="/outline" element={<OutlineBuilder />} />
                      <Route path="/admin" element={<AdminPanel />} />
                    </Routes>
                  </main>
                  <footer className="bg-white border-t mt-12 py-6">
                    <div className="container mx-auto px-4 text-center text-sm text-gray-600">
                      <p>© {new Date().getFullYear()} SMA Marketing. All rights reserved.</p>
                    </div>
                  </footer>
                </div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;

