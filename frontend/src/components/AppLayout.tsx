import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';

export function AppLayout({ children }: { children: ReactNode }) {
  return <div className="app-shell">
    <header className="site-header"><div className="header-inner">
      <Link className="brand" to="/" aria-label="Kana — trang chính"><span className="brand-mark" aria-hidden="true">あ</span><span className="brand-name">Kana<span className="brand-dot">.</span></span></Link>
      <nav className="header-nav" aria-label="Điều hướng chính">
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>Bài học</NavLink>
        <NavLink to="/history" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>Lịch sử</NavLink>
      </nav>
    </div></header>
    <main className="main-content">{children}</main>
    <footer className="site-footer"><span>Tiến độ lưu theo cookie trình duyệt. Xóa cookie hoặc đổi thiết bị sẽ có tiến độ riêng.</span><span lang="ja" className="footer-japanese">一歩ずつ</span></footer>
  </div>;
}
