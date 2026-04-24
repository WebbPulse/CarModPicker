import React, { useState } from 'react';
import { ErrorAlert } from './Alerts';
import Dialog from './Dialog';

interface DangerousActionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  actionName: string;
  confirmationPhrase: string;
  warningMessage: string;
  isProcessing: boolean;
  error: string | null;
}

const DangerousActionDialog: React.FC<DangerousActionDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  actionName,
  confirmationPhrase,
  warningMessage,
  isProcessing,
  error,
}) => {
  const [typedPhrase, setTypedPhrase] = useState('');
  const isConfirmed = typedPhrase === confirmationPhrase;

  const handleClose = () => {
    setTypedPhrase('');
    onClose();
  };

  const handleConfirm = () => {
    if (isConfirmed) {
      onConfirm();
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <Dialog
      isOpen={isOpen}
      onClose={handleClose}
      title={`⚠️ Dangerous Action: ${actionName}`}
      maxWidth="2xl"
    >
      <div className="text-neutral-300">
        <div className="mb-6 p-6 bg-red-900/30 border-2 border-red-700 rounded-xl">
          <p className="text-red-300 font-bold text-xl mb-3">
            ⚠️ WARNING: This action is irreversible!
          </p>
          <p className="text-red-200 text-lg leading-relaxed">
            {warningMessage}
          </p>
        </div>

        <div className="mb-6 p-4 bg-yellow-900/20 border border-yellow-700 rounded-lg">
          <p className="text-yellow-300 font-semibold mb-2">
            To confirm this action, please type:
          </p>
          <p className="text-yellow-200 font-mono text-lg bg-neutral-800 px-4 py-2 rounded border border-yellow-600">
            {confirmationPhrase}
          </p>
        </div>

        <div className="mb-6">
          <label
            htmlFor="confirmation-input"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Confirmation:
          </label>
          <input
            id="confirmation-input"
            type="text"
            value={typedPhrase}
            onChange={(e) => setTypedPhrase(e.target.value)}
            placeholder="Type the confirmation phrase above"
            className="w-full px-4 py-3 bg-neutral-800 border-2 border-neutral-700 rounded-xl text-white placeholder-neutral-500 focus:outline-none focus:border-red-600 focus:ring-2 focus:ring-red-600/50 transition-all"
            disabled={isProcessing}
            autoComplete="off"
          />
        </div>

        {error && (
          <div className="mb-6">
            <ErrorAlert message={error} />
          </div>
        )}

        <div className="flex justify-end space-x-3 mt-8">
          <button
            type="button"
            onClick={handleClose}
            className="glass-button px-6 py-3 rounded-xl text-neutral-300 hover:text-white transition-all duration-300"
            disabled={isProcessing}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!isConfirmed || isProcessing}
            className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
              isConfirmed
                ? 'bg-linear-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white hover:scale-105'
                : 'bg-neutral-700 text-neutral-400 cursor-not-allowed'
            }`}
          >
            {isProcessing ? 'Processing...' : `Confirm ${actionName}`}
          </button>
        </div>
      </div>
    </Dialog>
  );
};

export default DangerousActionDialog;
