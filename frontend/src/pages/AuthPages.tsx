import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, errorMessage } from '../api/client';
import type { AppConfig } from '../api/types';
import { useAuth } from '../components/AuthContext';
import { ThemeToggle } from '../components/ThemeMode';

function Brand() {
  return <Link className="brand auth-brand" to="/" aria-label="Kana — về bài học"><span className="brand-mark" aria-hidden="true">あ</span><span className="brand-name">Kana<span className="brand-dot">.</span></span></Link>;
}

export function LoginPage() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const response = await api.login({ email, password });
      setUser(response.user);
      navigate('/', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
      setPassword('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-theme-toggle"><ThemeToggle /></div>
      <section className="auth-card" aria-labelledby="login-heading">
        <Brand />
        <p className="eyebrow">TÀI KHOẢN</p>
        <h1 id="login-heading">Đăng nhập</h1>
        <p className="auth-intro">Đăng nhập để tiến độ học theo tài khoản, dùng được trên mọi thiết bị.</p>
        <form className="form-stack" onSubmit={(event) => void submit(event)}>
          {error && <p className="form-error" role="alert">{error}</p>}
          <label className="field-label">Email
            <input name="email" type="email" autoComplete="email" autoCapitalize="off" spellCheck={false} required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="field-label">Mật khẩu
            <input name="password" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button className="button button-primary button-wide" type="submit" disabled={busy}>{busy ? 'Đang kiểm tra…' : 'Đăng nhập'}</button>
        </form>
        <p className="auth-fineprint">Tiến độ học ẩn danh trên trình duyệt này không được gộp vào tài khoản có sẵn.</p>
        <p className="auth-switch">Chưa có tài khoản? <Link to="/register">Đăng ký</Link></p>
        <p className="auth-switch"><Link to="/">← Về bài học</Link></p>
      </section>
    </main>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api.config(controller.signal).then(setConfig).catch(() => undefined);
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const name = displayName.trim();
      const response = await api.register({
        email,
        password,
        ...(name ? { display_name: name } : {}),
        ...(config?.registration_code_required ? { registration_code: code } : {}),
      });
      setUser(response.user);
      navigate('/', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
      setPassword('');
    } finally {
      setBusy(false);
    }
  }

  const closed = config !== null && !config.registration_open;
  return (
    <main className="auth-page">
      <div className="auth-theme-toggle"><ThemeToggle /></div>
      <section className="auth-card" aria-labelledby="register-heading">
        <Brand />
        <p className="eyebrow">TÀI KHOẢN</p>
        <h1 id="register-heading">Tạo tài khoản</h1>
        <p className="auth-intro">Tiến độ bạn đã học trên trình duyệt này sẽ được giữ lại trong tài khoản mới.</p>
        {closed ? <p className="form-error" role="alert">Đăng ký tài khoản đang đóng.</p> : (
          <form className="form-stack" onSubmit={(event) => void submit(event)}>
            {error && <p className="form-error" role="alert">{error}</p>}
            <label className="field-label">Email
              <input name="email" type="email" autoComplete="email" autoCapitalize="off" spellCheck={false} required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="field-label">Tên hiển thị <span className="optional-label">(không bắt buộc)</span>
              <input name="display_name" autoComplete="nickname" maxLength={64} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </label>
            <label className="field-label">Mật khẩu
              <input name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
              <span className="field-hint">Ít nhất 8 ký tự.</span>
            </label>
            {config?.registration_code_required && (
              <label className="field-label">Mã đăng ký
                <input name="registration_code" autoComplete="off" required maxLength={256} value={code} onChange={(event) => setCode(event.target.value)} />
              </label>
            )}
            <button className="button button-primary button-wide" type="submit" disabled={busy}>{busy ? 'Đang tạo…' : 'Đăng ký'}</button>
          </form>
        )}
        <p className="auth-fineprint">Email chưa được xác minh và chưa có chức năng quên mật khẩu, hãy nhớ mật khẩu của bạn.</p>
        <p className="auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
        <p className="auth-switch"><Link to="/">← Về bài học</Link></p>
      </section>
    </main>
  );
}
