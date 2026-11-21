import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useAuth } from './AuthContext';
import { ThemeToggle } from './ThemeMode';

function AccountMenu() {
  const navigate = useNavigate();
  const { user, ready, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!ready) return null;
  if (!user) return <Link className="button button-small button-secondary" to="/login">Đăng nhập</Link>;

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await logout();
      navigate('/', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return <div className="account-menu">
    <span className="account-name" title={user.email ?? undefined}>{user.display_name}</span>
    <button className="button button-small button-quiet" type="button" onClick={() => void signOut()} disabled={busy}>Đăng xuất</button>
    {error && <span className="sr-only" role="alert">{error}</span>}
  </div>;
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <div className="app-shell">
    <header className="site-header"><div className="header-inner">
      <Link className="brand" to="/" aria-label="Kana — trang chính"><span className="brand-mark" aria-hidden="true">あ</span><span className="brand-name">Kana<span className="brand-dot">.</span></span></Link>
      <nav className="header-nav" aria-label="Điều hướng chính">
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>Bài học</NavLink>
        <NavLink to="/history" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>Lịch sử</NavLink>
      </nav>
      <ThemeToggle />
      <AccountMenu />
    </div></header>
    <main className="main-content">{children}</main>
    <footer className="site-footer"><span>{user
      ? 'Tiến độ được lưu theo tài khoản của bạn.'
      : 'Tiến độ lưu theo cookie trình duyệt. Xóa cookie hoặc đổi thiết bị sẽ có tiến độ riêng. Đăng nhập để giữ tiến độ.'}</span><span lang="ja" className="footer-japanese">一歩ずつ</span></footer>
  </div>;
}
