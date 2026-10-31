import { useCallback, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, errorMessage, isApiError } from '../api/client';
import type { AdminOverview } from '../api/types';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

const numberFormat = new Intl.NumberFormat('vi-VN');

/** "2026-10-30" (UTC day) → "30/10". */
function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split('-');
  return `${day}/${month}`;
}

function Brand() {
  return <Link className="brand auth-brand" to="/" aria-label="Kana — về bài học"><span className="brand-mark" aria-hidden="true">あ</span><span className="brand-name">Kana<span className="brand-dot">.</span></span></Link>;
}

export function AdminLoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await api.adminLogin({ username, password });
      setPassword('');
      navigate('/admin', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
      setPassword('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="admin-login-heading">
        <Brand />
        <p className="eyebrow">KHU VỰC QUẢN TRỊ</p>
        <h1 id="admin-login-heading">Đăng nhập quản trị</h1>
        <p className="auth-intro">Người học không cần đăng nhập. Trang này chỉ dành cho quản trị viên.</p>
        <form className="form-stack" onSubmit={(event) => void submit(event)}>
          {error && <p className="form-error" role="alert">{error}</p>}
          <label className="field-label">Tên đăng nhập
            <input name="username" autoComplete="username" autoCapitalize="off" spellCheck={false} required maxLength={64} value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label className="field-label">Mật khẩu
            <input name="password" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button className="button button-primary button-wide" type="submit" disabled={busy}>{busy ? 'Đang kiểm tra…' : 'Đăng nhập'}</button>
        </form>
        <p className="auth-switch"><Link to="/">← Về bài học</Link></p>
      </section>
    </main>
  );
}

function AdminShell({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header"><div className="header-inner">
        <Brand />
        <span className="admin-label">Quản trị</span>
        <div className="admin-actions">{actions}</div>
      </div></header>
      <main className="main-content">{children}</main>
    </div>
  );
}

function VisitsChart({ days }: { days: AdminOverview['visits_by_day'] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(0, ...days.map((day) => day.visits));
  const total = days.reduce((sum, day) => sum + day.visits, 0);
  const shown = active === null ? null : days[active];
  if (max === 0) return <p className="admin-empty">Chưa có lượt truy cập nào trong 30 ngày qua.</p>;
  return (
    <figure className="visits-chart">
      <p className="visits-readout" aria-hidden="true">
        {shown ? <><strong>{numberFormat.format(shown.visits)}</strong> lượt · {shortDate(shown.date)}</> : <>Tổng <strong>{numberFormat.format(total)}</strong> lượt · rê chuột hoặc chạm vào cột để xem từng ngày</>}
      </p>
      <div className="visits-plot" aria-hidden="true" onPointerLeave={() => setActive(null)}>
        <span className="visits-max">{numberFormat.format(max)}</span>
        {days.map((day, index) => (
          <span key={day.date} className={`visits-column${active === index ? ' is-active' : ''}`} onPointerEnter={() => setActive(index)} onPointerDown={() => setActive(index)}>
            {day.visits > 0 && <span className="visits-bar" style={{ height: `${(day.visits / max) * 100}%` }} />}
          </span>
        ))}
      </div>
      <div className="visits-axis" aria-hidden="true">
        <span>{shortDate(days[0]!.date)}</span>
        <span>{shortDate(days[days.length - 1]!.date)}</span>
      </div>
      <figcaption className="sr-only">Biểu đồ cột lượt truy cập theo ngày; số liệu chi tiết nằm trong bảng bên dưới.</figcaption>
    </figure>
  );
}

export function AdminPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      setData(await api.adminOverview(signal));
    } catch (caught) {
      if (signal?.aborted) return;
      if (isApiError(caught) && caught.status === 401) {
        navigate('/admin/login', { replace: true });
        return;
      }
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function logout() {
    setBusy(true);
    try {
      await api.adminLogout();
      navigate('/admin/login', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const actions = <>
    <button className="button button-secondary button-small" type="button" disabled={loading} onClick={() => void load()}>Làm mới</button>
    <button className="button button-quiet button-small" type="button" disabled={busy} onClick={() => void logout()}>Đăng xuất</button>
  </>;

  if (loading && !data) return <AdminShell><PageStatus label="Đang tải thống kê…" /></AdminShell>;
  if (!data) return <AdminShell actions={actions}><LoadError message={error} onRetry={() => void load()} /></AdminShell>;

  const tiles: [string, number, string][] = [
    ['Trình duyệt đã ghé', data.visitors_total, 'Mỗi trình duyệt có cookie riêng, không phải số người chính xác.'],
    ['Hoạt động 7 ngày', data.active_learners_7d, 'Trình duyệt có yêu cầu trong 7 ngày gần nhất.'],
    ['Lượt luyện 15 phút', data.active_sessions_15m, 'Lượt luyện được tạo hoặc có câu trả lời trong 15 phút qua.'],
    ['Câu hỏi đã tạo', data.questions_in_sessions, 'Tổng số câu trong mọi lượt luyện.'],
    ['Câu trả lời đã nộp', data.answers_submitted, 'Tính cả lựa chọn “Không biết”.'],
  ];

  return (
    <AdminShell actions={actions}>
      <div className="page-stack admin-page">
        <div className="page-heading-block">
          <p className="eyebrow">THỐNG KÊ SỬ DỤNG</p>
          <h1>Tổng quan</h1>
          <p>Chỉ số liệu tổng hợp — không có IP, danh tính hay nội dung câu trả lời của người học.</p>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="admin-stats">
          {tiles.map(([label, value, hint]) => (
            <section className="admin-stat" key={label}>
              <p className="admin-stat-label">{label}</p>
              <p className="admin-stat-value">{numberFormat.format(value)}</p>
              <p className="admin-stat-hint">{hint}</p>
            </section>
          ))}
        </div>
        <section className="admin-panel" aria-labelledby="visits-heading">
          <div className="section-heading">
            <div><p className="eyebrow">30 NGÀY GẦN NHẤT · GIỜ UTC</p><h2 id="visits-heading">Lượt truy cập theo ngày</h2></div>
          </div>
          <p className="admin-note">Một lượt được tính khi trình duyệt quay lại sau ít nhất 30 phút không hoạt động. Dữ liệu lượt truy cập được giữ tối đa 90 ngày.</p>
          <VisitsChart days={data.visits_by_day} />
          <details className="admin-table-toggle">
            <summary>Xem dạng bảng</summary>
            <table className="admin-table">
              <thead><tr><th scope="col">Ngày (UTC)</th><th scope="col">Lượt truy cập</th></tr></thead>
              <tbody>{[...data.visits_by_day].reverse().map((row) => <tr key={row.date}><td>{row.date}</td><td>{numberFormat.format(row.visits)}</td></tr>)}</tbody>
            </table>
          </details>
        </section>
      </div>
    </AdminShell>
  );
}
