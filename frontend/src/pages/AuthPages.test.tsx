import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '../api/client';
import type { AppConfig, AuthUser } from '../api/types';
import { AppLayout } from '../components/AppLayout';
import { AuthProvider } from '../components/AuthContext';
import { ThemeModeProvider } from '../components/ThemeMode';
import { LoginPage, RegisterPage } from './AuthPages';

vi.mock('../api/client', async (importOriginal: () => Promise<{ api: typeof api }>) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: {
      ...actual.api,
      me: vi.fn(),
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      initLearner: vi.fn(),
      config: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);

const user: AuthUser = {
  id: 7,
  email: 'learner@example.com',
  display_name: 'Lan',
  created_at: '2026-11-21T00:00:00Z',
};
const openConfig: AppConfig = {
  registration_open: true,
  registration_code_required: false,
  session_size: 20,
  focus_size: 5,
};

function renderAt(path: string) {
  return render(
    <ThemeModeProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/" element={<AppLayout><h1>Trang chính</h1></AppLayout>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </ThemeModeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.me.mockResolvedValue({ user: null });
  mockedApi.config.mockResolvedValue(openConfig);
  mockedApi.initLearner.mockResolvedValue({ status: 'ok' });
  mockedApi.logout.mockResolvedValue(undefined);
});

describe('LoginPage', () => {
  it('signs in and returns to the home page with the account menu', async () => {
    mockedApi.login.mockResolvedValue({ user });
    renderAt('/login');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'secret-pass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(await screen.findByRole('heading', { name: 'Trang chính' })).toBeInTheDocument();
    expect(mockedApi.login).toHaveBeenCalledWith({ email: 'learner@example.com', password: 'secret-pass' });
    expect(screen.getByText('Lan')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeInTheDocument();
  });

  it('shows the server message and clears the password after a failure', async () => {
    mockedApi.login.mockRejectedValue(new ApiError(401, 'Email hoặc mật khẩu không đúng.'));
    renderAt('/login');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'bad-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email hoặc mật khẩu không đúng.');
    expect(screen.getByLabelText('Mật khẩu')).toHaveValue('');
    expect(screen.getByLabelText('Email')).toHaveValue('learner@example.com');
  });
});

describe('RegisterPage', () => {
  it('registers with an optional display name and signs in', async () => {
    mockedApi.register.mockResolvedValue({ user });
    renderAt('/register');
    await waitFor(() => expect(mockedApi.config).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText(/Tên hiển thị/), { target: { value: '  Lan  ' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu/), { target: { value: 'secret-pass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng ký' }));
    expect(await screen.findByRole('heading', { name: 'Trang chính' })).toBeInTheDocument();
    expect(mockedApi.register).toHaveBeenCalledWith({
      email: 'learner@example.com',
      password: 'secret-pass',
      display_name: 'Lan',
    });
  });

  it('omits the display name when left blank', async () => {
    mockedApi.register.mockResolvedValue({ user });
    renderAt('/register');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu/), { target: { value: 'secret-pass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng ký' }));
    await screen.findByRole('heading', { name: 'Trang chính' });
    expect(mockedApi.register).toHaveBeenCalledWith({ email: 'learner@example.com', password: 'secret-pass' });
  });

  it('asks for the registration code only when the server requires one', async () => {
    mockedApi.config.mockResolvedValue({ ...openConfig, registration_code_required: true });
    mockedApi.register.mockResolvedValue({ user });
    renderAt('/register');
    const code = await screen.findByLabelText('Mã đăng ký');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu/), { target: { value: 'secret-pass' } });
    fireEvent.change(code, { target: { value: 'open-sesame' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng ký' }));
    await screen.findByRole('heading', { name: 'Trang chính' });
    expect(mockedApi.register).toHaveBeenCalledWith({
      email: 'learner@example.com',
      password: 'secret-pass',
      registration_code: 'open-sesame',
    });
  });

  it('shows a conflict message for an existing email', async () => {
    mockedApi.register.mockRejectedValue(new ApiError(409, 'Email này đã được đăng ký.'));
    renderAt('/register');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'learner@example.com' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu/), { target: { value: 'secret-pass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng ký' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email này đã được đăng ký.');
  });

  it('hides the form when registration is closed', async () => {
    mockedApi.config.mockResolvedValue({ ...openConfig, registration_open: false });
    renderAt('/register');
    expect(await screen.findByRole('alert')).toHaveTextContent('Đăng ký tài khoản đang đóng.');
    expect(screen.queryByRole('button', { name: 'Đăng ký' })).not.toBeInTheDocument();
  });
});

describe('AppLayout account menu', () => {
  it('offers sign-in to an anonymous browser', async () => {
    renderAt('/');
    expect(await screen.findByRole('link', { name: 'Đăng nhập' })).toHaveAttribute('href', '/login');
    expect(screen.getByText(/Đăng nhập để giữ tiến độ/)).toBeInTheDocument();
  });

  it('signs out and re-issues the anonymous identity before updating the UI', async () => {
    mockedApi.me.mockResolvedValue({ user });
    renderAt('/');
    fireEvent.click(await screen.findByRole('button', { name: 'Đăng xuất' }));
    expect(await screen.findByRole('link', { name: 'Đăng nhập' })).toBeInTheDocument();
    expect(mockedApi.logout).toHaveBeenCalledTimes(1);
    expect(mockedApi.initLearner).toHaveBeenCalledTimes(1);
    expect(mockedApi.logout.mock.invocationCallOrder[0]!).toBeLessThan(
      mockedApi.initLearner.mock.invocationCallOrder[0]!,
    );
  });
});
