import { useNavigate } from 'react-router-dom';

export function LoadError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const navigate = useNavigate();
  return (
    <section className="state-card" role="alert">
      <span className="state-icon state-icon-error" aria-hidden="true">!</span>
      <h2>Chưa tải được nội dung</h2>
      <p>{message}</p>
      <div className="button-row">
        {onRetry && <button className="button button-secondary" type="button" onClick={onRetry}>Thử lại</button>}
        <button className="button button-quiet" type="button" onClick={() => navigate('/')}>Về trang chính</button>
      </div>
    </section>
  );
}
