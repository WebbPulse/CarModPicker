import React from 'react';
import { createPortal } from 'react-dom';

interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl' | '6xl';
}

const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'lg',
}) => {
  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '4xl': 'max-w-4xl',
    '6xl': 'max-w-6xl',
  };

  const dialog = (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4 transition-all duration-300 ease-in-out">
      <div
        className={`bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full ${maxWidthClasses[maxWidth]} transform transition-all duration-300 ease-in-out scale-95 opacity-0 animate-fadeInScale flex flex-col max-h-[90vh]`}
      >
        <div className="flex-shrink-0 p-6 border-b border-white/10">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-neutral-300 bg-clip-text text-transparent">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-neutral-400 hover:text-white text-2xl leading-none p-2 hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-110"
              aria-label="Close dialog"
            >
              &times;
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-6">{children}</div>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
};

export default Dialog;
