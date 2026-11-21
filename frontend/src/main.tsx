import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppRouter } from './app/Router';
import { ThemeModeProvider } from './components/ThemeMode';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeModeProvider><AppRouter /></ThemeModeProvider>
  </React.StrictMode>,
);
