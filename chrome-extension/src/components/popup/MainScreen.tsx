import React from 'react';
import type { User } from '../../types';

interface MainScreenProps {
  user: User;
  onLogout: () => void;
  onScrape: () => void;
  statusMessage: { message: string; type: 'info' | 'success' | 'error' } | null;
}

const MainScreen: React.FC<MainScreenProps> = ({ user, onLogout, onScrape, statusMessage }) => {
  const statusClasses = {
    success: 'bg-green-500/20 border border-green-500/50 text-green-200',
    error: 'bg-red-500/20 border border-red-500/50 text-red-200',
    info: 'bg-blue-500/20 border border-blue-500/50 text-blue-200',
  };

  return (
    <div className="p-5">
      <div className="mb-6">
        <div className="flex justify-between items-center">
          <span className="font-medium text-white">
            {user.username || user.email || 'User'}
          </span>
          <button
            onClick={onLogout}
            className="text-primary-400 text-xs hover:text-primary-300 transition-colors underline"
          >
            Logout
          </button>
        </div>
      </div>

      <button
        onClick={onScrape}
        className="w-full py-4 px-6 rounded-xl font-semibold text-lg bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(59,130,246,0.3)]"
      >
        <span>📦</span>
        <span>Scrape Current Page</span>
      </button>

      {statusMessage && (
        <div
          className={`mt-4 p-3 border rounded-xl text-sm text-center ${
            statusClasses[statusMessage.type]
          }`}
        >
          {statusMessage.message}
        </div>
      )}
    </div>
  );
};

export default MainScreen;
