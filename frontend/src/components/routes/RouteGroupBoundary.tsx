import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '../ui/button';

/**
 * The four route groups the app wraps in their own error boundaries.
 */
export type RouteGroupName = 'admin' | 'authentication' | 'builder' | 'public';

interface FallbackProps {
  groupName: RouteGroupName;
  error: Error | null;
  onRetry: () => void;
}

/** The contained fallback for one route group, with Retry and Go Home. */
function RouteGroupFallback({ groupName, error, onRetry }: FallbackProps) {
  const navigate = useNavigate();
  const handleGoHome = () => {
    void navigate('/');
  };
  return (
    <section
      data-route-group={groupName}
      className="container mx-auto px-4 py-16"
    >
      <div className="mx-auto max-w-lg p-8 bg-card/50 rounded-xl text-foreground">
        <h2 className="text-2xl font-semibold text-foreground mb-3">
          Something went wrong in the {groupName} section
        </h2>
        <p className="text-sm text-muted-foreground mb-6">
          {error instanceof Error ? error.message : 'Unknown error'}
        </p>
        <div className="flex gap-3">
          <Button type="button" onClick={onRetry}>
            Retry
          </Button>
          <Button type="button" variant="secondary" onClick={handleGoHome}>
            Go Home
          </Button>
        </div>
      </div>
    </section>
  );
}

interface Props {
  groupName: RouteGroupName;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Wraps one route group in an error boundary so a throw inside it does not
 * blank the app, and offers Retry and Go Home.
 */
export class RouteGroupBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      `RouteGroupBoundary (${this.props.groupName}) caught an error:`,
      error,
      errorInfo
    );
  }

  private handleRetry = () => {
    this.setState({ error: null });
  };

  override render() {
    if (this.state.error) {
      return (
        <RouteGroupFallback
          groupName={this.props.groupName}
          error={this.state.error}
          onRetry={this.handleRetry}
        />
      );
    }
    return this.props.children;
  }
}

export default RouteGroupBoundary;
