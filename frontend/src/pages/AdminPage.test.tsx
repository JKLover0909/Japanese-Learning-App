import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '../api/client';
import type { AdminOverview } from '../api/types';
import { AdminLoginPage, AdminPage } from './AdminPage';

vi.mock('../api/client', async (importOriginal: () => Promise<{ api: typeof api }>) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: { ...actual.api, adminLogin: vi.fn(), adminLogout: vi.fn(), adminOverview: vi.fn() },
  };
});

const mockedApi = vi.mocked(api);

const overview: AdminOverview = {
  visitors_total: 1234, active_learners_7d: 56, active_sessions_15m: 3,
  questions_in_sessions: 4000, answers_submitted: 3210,
  visits_by_day: Array.from({ length: 30 }, (_, index) => ({
    date: `2026-10-${String(index + 1).padStart(2, '0')}`,
    visits: index === 29 ? 42 : 0,
  })),
};

function renderAdmin(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/login" element={<AdminLoginPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AdminPage', () => {
  it('redirects to the admin login when the session is missing', async () => {
    mockedApi.adminOverview.mockRejectedValue(new ApiError(401, 'Vui lòng đăng nhập quản trị.'));
    renderAdmin('/admin');
    expect(await screen.findByRole('heading', { name: 'Đăng nhập quản trị' })).toBeInTheDocument();
  });

  it('shows only aggregate counts and a table view of daily visits', async () => {
    mockedApi.adminOverview.mockResolvedValue(overview);
    renderAdmin('/admin');
    expect(await screen.findByText('Trình duyệt đã ghé')).toBeInTheDocument();
    expect(screen.getByText(new Intl.NumberFormat('vi-VN').format(1234))).toBeInTheDocument();
    const rows = screen.getAllByRole('row');
    expect(rows).toHaveLength(31);
    expect(rows[1]).toHaveTextContent('2026-10-30');
    expect(rows[1]).toHaveTextContent('42');
  });

  it('clears the password after a failed admin login', async () => {
    mockedApi.adminLogin.mockRejectedValue(new ApiError(401, 'Tên đăng nhập hoặc mật khẩu không đúng.'));
    renderAdmin('/admin/login');
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Tên đăng nhập hoặc mật khẩu không đúng.');
    expect(mockedApi.adminLogin).toHaveBeenCalledWith({ username: 'admin', password: 'wrong-password' });
    expect(screen.getByLabelText('Mật khẩu')).toHaveValue('');
  });

  it('opens the overview after a successful admin login', async () => {
    mockedApi.adminLogin.mockResolvedValue({ status: 'ok' });
    mockedApi.adminOverview.mockResolvedValue(overview);
    renderAdmin('/admin/login');
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'right-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));

    expect(await screen.findByRole('heading', { name: 'Tổng quan' })).toBeInTheDocument();
  });
});
