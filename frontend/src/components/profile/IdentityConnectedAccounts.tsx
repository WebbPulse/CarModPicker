/**
 * The connected accounts panel for identity mode: link and unlink providers.
 * The state machine is `useConnectedAccountsPanel` and the provider list is
 * `useOAuthProviders`; this file is the markup. Linking is a full-page
 * navigation because the start route redirects to a host that sends no CORS
 * headers; the callback returns with a marker in the query.
 */
import { FaGithub, FaGoogle, FaLink, FaTrash } from 'react-icons/fa';
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';
import { useConnectedAccountsPanel } from '@webbpulse/auth/panels';
import { useOAuthProviders } from '@webbpulse/discovery/react';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import Spinner from '../ui/spinner';
import {
  getIdentityClient,
  identityOrigin,
  type IdentityClient,
} from '../../api/identityClient';

/** A date for display, falling back to the raw value rather than throwing. */
const formatDate = (value: string | undefined): string => {
  if (!value) return 'Unknown';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
};

/** The provider's mark, where this build has one. */
const ProviderIcon: React.FC<{ provider: string }> = ({ provider }) => {
  if (provider === GOOGLE_PROVIDER) return <FaGoogle />;
  if (provider === GITHUB_PROVIDER) return <FaGithub />;
  return <FaLink />;
};

/** The panel body, mounted only once the identity client could be built. */
const ConnectedAccountsBody: React.FC<{ client: IdentityClient }> = ({
  client,
}) => {
  const providers = useOAuthProviders({ identityOrigin: identityOrigin() });
  const panel = useConnectedAccountsPanel({
    client,
    providers,
    returnTo: `${globalThis.location.pathname}${globalThis.location.search}`,
    messages: {
      removed: (provider: string) =>
        `${providers.find((entry) => entry.id === provider)?.displayName ?? provider} disconnected.`,
    },
  });

  if (panel.loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const links = panel.items ?? [];
  const label = (provider: string): string =>
    providers.find((entry) => entry.id === provider)?.displayName ?? provider;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Connected accounts</h3>
        <p className="text-sm text-muted-foreground">
          Sign in to CarModPicker with an account you already have.
        </p>
      </div>

      {panel.error && <ErrorAlert message={panel.error} />}
      {panel.notice && <ConfirmationAlert message={panel.notice} />}

      {providers.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No sign in providers are configured for this deployment.
        </p>
      )}

      {links.length > 0 && (
        <ul className="space-y-2">
          {links.map((link) => (
            <li
              key={link.provider}
              className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="shrink-0 text-primary">
                  <ProviderIcon provider={link.provider} />
                </span>
                <div className="min-w-0">
                  <div className="truncate font-medium text-white">
                    {label(link.provider)}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {link.email || 'Connected'} · since{' '}
                    {formatDate(link.linkedAt)}
                  </div>
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                aria-label={`Disconnect ${label(link.provider)}`}
                onClick={() => {
                  if (
                    !window.confirm(
                      `Disconnect your ${label(link.provider)} account?`
                    )
                  ) {
                    return;
                  }
                  void panel.unlink(link.provider);
                }}
                disabled={
                  panel.busy || panel.blocked[link.provider] !== undefined
                }
              >
                <FaTrash />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {panel.connectable.length > 0 && (
        <div className="space-y-2">
          {panel.connectable.map((provider) => (
            <Button
              key={provider.id}
              type="button"
              variant="secondary"
              className="w-full"
              onClick={() => void panel.link(provider.id)}
              disabled={panel.busy}
            >
              <ProviderIcon provider={provider.id} />
              <span>Connect {provider.displayName}</span>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
};

/** The connected accounts panel, or the unavailable notice in bearer mode. */
function IdentityConnectedAccounts() {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <ErrorAlert message="Connected accounts are not available in this deployment." />
    );
  }
  return <ConnectedAccountsBody client={client} />;
}

export default IdentityConnectedAccounts;
