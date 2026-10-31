import { useEffect, useState } from 'react';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { api, errorMessage } from '../api/client';
import { AppLayout } from '../components/AppLayout';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';
import { DashboardPage } from '../pages/DashboardPage';
import { HistoryPage } from '../pages/HistoryPage';
import { LessonPage } from '../pages/LessonPage';
import { PracticePage } from '../pages/PracticePage';
import { SummaryPage } from '../pages/SummaryPage';
import { AdminLoginPage, AdminPage } from '../pages/AdminPage';
import { ChapterTestPage } from '../pages/ChapterTestPage';
import { ChapterTestResultPage } from '../pages/ChapterTestResultPage';

let initialization: Promise<unknown> | null = null;
function initializeLearner() {
  if (!initialization) initialization = api.initLearner().catch((error: unknown) => {
    initialization = null;
    throw error;
  });
  return initialization;
}

function LearnerOutlet() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void initializeLearner().then(() => { if (active) setReady(true); })
      .catch((caught) => { if (active) setError(errorMessage(caught)); });
    return () => { active = false; };
  }, []);
  if (error) return <main className="main-content"><LoadError message={error} onRetry={() => window.location.reload()} /></main>;
  if (!ready) return <PageStatus label="Đang mở góc học…" />;
  return <AppLayout><Outlet /></AppLayout>;
}

export function AppRouter() {
  return <BrowserRouter><Routes>
    <Route path="/login" element={<Navigate to="/" replace />} />
    <Route path="/register" element={<Navigate to="/" replace />} />
    <Route path="/admin/login" element={<AdminLoginPage />} />
    <Route path="/admin" element={<AdminPage />} />
    <Route element={<LearnerOutlet />}>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/lessons/:slug" element={<LessonPage />} />
      <Route path="/practice/:sessionId" element={<PracticePage />} />
      <Route path="/sessions/:id/summary" element={<SummaryPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/tests/:testId" element={<ChapterTestPage />} />
      <Route path="/tests/:testId/result" element={<ChapterTestResultPage />} />
    </Route>
    <Route path="*" element={<main className="status-page"><h1>Không tìm thấy trang</h1><Link to="/">Về bài học</Link></main>} />
  </Routes></BrowserRouter>;
}
