import { useAuth } from "./hooks/useAuth";
import AuthPage from "./pages/AuthPage";
import BoardPage from "./pages/BoardPage";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="splash" aria-busy="true">Loading…</div>;
  return user ? <BoardPage user={user} /> : <AuthPage />;
}
