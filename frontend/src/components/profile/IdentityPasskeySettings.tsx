/**
 * The passkeys panel for identity mode: enrol, rename, delete. The state
 * machine is `usePasskeyPanel` from `@webbpulse/auth/panels`; this file is the
 * markup and the deployment availability gate. Server refusals are surfaced
 * verbatim because they name the user's next step.
 */
import { useEffect, useState } from 'react';
import { FaKey, FaPencilAlt, FaPlus, FaTrash } from 'react-icons/fa';
import { usePasskeyPanel } from '@webbpulse/auth/panels';
import type { Passkey } from '@webbpulse/auth';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';
import {
  PASSKEY_AVAILABILITY_PATH,
  getIdentityClient,
  identityUrl,
  passkeyEnrolmentAvailability,
  type Availability,
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

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Passkeys are not available in this deployment.';

/** The heading and one sentence, for the two states with no list to show. */
const PasskeyNotice: React.FC<{ message: string }> = ({ message }) => (
  <div className="space-y-4">
    <div>
      <h3 className="text-lg font-semibold text-white">Passkeys</h3>
    </div>
    <p className="text-sm text-muted-foreground">{message}</p>
  </div>
);

/** The panel body, mounted only once the deployment said passkeys are on. */
const PasskeyPanelBody: React.FC<{ client: IdentityClient }> = ({ client }) => {
  const panel = usePasskeyPanel({
    client,
    messages: {
      created: (passkey: Passkey) => `Passkey "${passkey.name}" added.`,
      renamed: 'Passkey renamed.',
      removed: 'Passkey removed.',
    },
  });

  if (panel.loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const passkeys = panel.items ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Passkeys</h3>
        <p className="text-sm text-muted-foreground">
          Sign in with your fingerprint, face, screen lock or a security key
          instead of a password.
        </p>
      </div>

      {panel.error && <ErrorAlert message={panel.error} />}
      {panel.notice && <ConfirmationAlert message={panel.notice} />}

      {!panel.supported && (
        <p className="text-sm text-muted-foreground">
          This browser cannot use passkeys. Your existing passkeys are listed
          below and still work in a browser that can.
        </p>
      )}

      {passkeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          You have not added a passkey yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {passkeys.map((passkey) => (
            <li
              key={passkey.credentialId}
              className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
            >
              {panel.renaming === passkey.credentialId ? (
                <>
                  <Input
                    aria-label="Passkey name"
                    value={panel.draftRename}
                    onChange={(e) => panel.setDraftRename(e.target.value)}
                    disabled={panel.busy}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => void panel.commitRename()}
                    disabled={panel.busy}
                  >
                    Save
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={panel.cancelRename}
                    disabled={panel.busy}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <>
                  <div className="flex min-w-0 items-center gap-3">
                    <FaKey className="shrink-0 text-primary" />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-white">
                        {passkey.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Added {formatDate(passkey.createdAt)}
                        {passkey.lastUsedAt
                          ? ` · Last used ${formatDate(passkey.lastUsedAt)}`
                          : ''}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      aria-label={`Rename ${passkey.name}`}
                      onClick={() => {
                        panel.dismiss();
                        panel.startRename(passkey);
                      }}
                      disabled={panel.busy}
                    >
                      <FaPencilAlt />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      aria-label={`Remove ${passkey.name}`}
                      onClick={() => {
                        if (
                          !window.confirm(
                            `Remove "${passkey.name}"? You will not be able to sign in with it again.`
                          )
                        ) {
                          return;
                        }
                        void panel.remove(passkey.credentialId);
                      }}
                      disabled={panel.busy}
                    >
                      <FaTrash />
                    </Button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {panel.adding ? (
        <div className="space-y-3 rounded-lg border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="passkey-name"
            className="block text-sm font-medium text-foreground"
          >
            Name this passkey
          </label>
          <Input
            id="passkey-name"
            value={panel.draftName}
            onChange={(e) => panel.setDraftName(e.target.value)}
            placeholder="Laptop, phone, security key"
            disabled={panel.busy}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              onClick={() => void panel.commitCreate()}
              disabled={panel.busy}
              loading={panel.busy}
            >
              {panel.busy ? 'Waiting for your device…' : 'Add passkey'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={panel.cancelCreate}
              disabled={panel.busy}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        panel.supported && (
          <Button
            type="button"
            onClick={() => {
              panel.dismiss();
              panel.startCreate();
            }}
            disabled={panel.busy}
          >
            <FaPlus />
            <span>Add a passkey</span>
          </Button>
        )
      )}
    </div>
  );
};

/**
 * The passkeys panel, gated on the deployment's enrolment availability so a
 * deployment with passkeys off renders the notice rather than an empty list.
 */
function IdentityPasskeySettings() {
  const [availability, setAvailability] = useState<Availability | null>(null);

  useEffect(() => {
    let cancelled = false;
    void passkeyEnrolmentAvailability(
      identityUrl(PASSKEY_AVAILABILITY_PATH)
    ).then((answer) => {
      if (!cancelled) setAvailability(answer);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (availability === null) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (availability === 'unavailable') {
    return <PasskeyNotice message={UNAVAILABLE} />;
  }

  const client = getIdentityClient();
  if (client === null) {
    return <PasskeyNotice message={UNAVAILABLE} />;
  }

  return <PasskeyPanelBody client={client} />;
}

export default IdentityPasskeySettings;
