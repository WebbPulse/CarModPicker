import { useState } from 'react';
import { FaCreditCard } from 'react-icons/fa';

import { createPortalSession, redirectToBilling } from '../../api/billing';
import { getPortalErrorMessage } from '../../utils/billingErrors';
import { ErrorAlert } from '../ui/alert';
import { Button, type ButtonProps } from '../ui/button';

/** Props for ManageSubscriptionButton. */
interface ManageSubscriptionButtonProps {
  className?: string;
  variant?: ButtonProps['variant'];
}

/**
 * Opens the Stripe Customer Portal for the signed in subscriber, with a
 * loading state and an inline error when the portal session fails.
 */
function ManageSubscriptionButton({
  className,
  variant,
}: ManageSubscriptionButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setError(null);
    setIsLoading(true);
    try {
      redirectToBilling(await createPortalSession());
    } catch (err) {
      setError(getPortalErrorMessage(err));
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <Button
        type="button"
        variant={variant}
        className={className}
        loading={isLoading}
        onClick={() => void handleClick()}
      >
        {!isLoading && <FaCreditCard />}
        Manage subscription
      </Button>
      <ErrorAlert message={error} />
    </div>
  );
}

export default ManageSubscriptionButton;
