import { useState } from 'react';
import { FaTimes, FaWrench } from 'react-icons/fa';

const SESSION_KEY = 'beta_banner_dismissed';

function BetaBanner() {
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(SESSION_KEY) === 'true'
  );

  if (dismissed) return null;

  const handleDismiss = () => {
    sessionStorage.setItem(SESSION_KEY, 'true');
    setDismissed(true);
  };

  return (
    <div className="relative z-40 w-full bg-amber-500/15 border-b border-amber-500/30 backdrop-blur-sm">
      <div className="container mx-auto px-4 py-2.5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5 text-amber-300 text-sm">
          <FaWrench className="shrink-0 text-amber-400" />
          <span>
            <span className="font-semibold">
              CarModPicker is under active development.
            </span>{' '}
            Data wipes may occur before the official launch. Thanks for testing!
          </span>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss banner"
          className="shrink-0 text-amber-400 hover:text-amber-200 transition-colors duration-200"
        >
          <FaTimes />
        </button>
      </div>
    </div>
  );
}

export default BetaBanner;
