/**
 * The "Continue with X" buttons for identity mode, one per provider
 * `useOAuthProviders` reports, with `useOAuthProviderLinks` building each start
 * URL. Rendered as anchors because the start route redirects to a host that
 * sends no CORS headers, so it must be a real navigation.
 */
import { FaGithub, FaGoogle, FaSignInAlt } from 'react-icons/fa';
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';
import { useOAuthProviderLinks } from '@webbpulse/auth/react';
import { useOAuthProviders } from '@webbpulse/discovery/react';
import { getIdentityClient, identityOrigin } from '../../api/identityClient';

/** Props for OAuthProviderButtons: where to land after the callback. */
export interface OAuthProviderButtonsProps {
  /** Where to land after the callback, as a path on this frontend. */
  returnTo?: string;
  disabled?: boolean;
}

/** The provider's mark, where this build has one. */
const ProviderIcon: React.FC<{ provider: string }> = ({ provider }) => {
  if (provider === GOOGLE_PROVIDER) return <FaGoogle />;
  if (provider === GITHUB_PROVIDER) return <FaGithub />;
  return <FaSignInAlt />;
};

function OAuthProviderButtons({
  returnTo,
  disabled,
}: OAuthProviderButtonsProps) {
  const providers = useOAuthProviders({ identityOrigin: identityOrigin() });
  const links = useOAuthProviderLinks({
    client: getIdentityClient(),
    providers,
    ...(returnTo === undefined ? {} : { returnTo }),
  });

  if (links.length === 0) return null;

  return (
    <div className="space-y-2">
      {links.map((link) => (
        <a
          key={link.id}
          href={disabled ? undefined : link.href}
          aria-disabled={disabled ? 'true' : undefined}
          className={`inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-md border border-white/10 bg-white/5 px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-white/10 ${
            disabled ? 'pointer-events-none opacity-50' : ''
          }`}
        >
          <ProviderIcon provider={link.id} />
          <span>Continue with {link.displayName}</span>
        </a>
      ))}
    </div>
  );
}

export default OAuthProviderButtons;
