/**
 * The TOTP panel for identity mode: enrol, disable, and replace recovery codes.
 * The state machine is `useTotpPanel` from `@webbpulse/auth/panels`; this file
 * is the markup. Recovery codes are issued once on activation and sit behind a
 * confirmation, since the server keeps only hashes and cannot show them again.
 */
import React, { useCallback, useState } from 'react';
import { FaShieldAlt } from 'react-icons/fa';
import { useTotpPanel, type TotpPanel } from '@webbpulse/auth/panels';
import { qrCodeSvgPath } from '@webbpulse/qrcode';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import {
  getIdentityClient,
  type IdentityClient,
} from '../../api/identityClient';

/** The sentence shown when the request never reached the server. */
const UNREACHABLE = 'Could not reach the server. Check your connection.';

/** The provisioning URI as a scannable QR code. */
const ProvisioningQr: React.FC<{ uri: string }> = ({ uri }) => {
  let code: { path: string; viewBox: string };
  try {
    code = qrCodeSvgPath(uri);
  } catch {
    return null;
  }
  return (
    <svg
      viewBox={code.viewBox}
      className="w-48 h-48 bg-white p-2 rounded-lg"
      role="img"
      aria-label="Two factor authentication QR code"
    >
      <path d={code.path} fill="#000000" />
    </svg>
  );
};

/** The one-time recovery codes, behind a confirmation. */
const RecoveryCodes: React.FC<{ codes: string[]; onDone: () => void }> = ({
  codes,
  onDone,
}) => {
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-4">
      <ConfirmationAlert message="Two factor authentication is on. Save these recovery codes now." />
      <p className="text-sm text-gray-400">
        Each code signs you in once if you lose your authenticator app. They are
        shown here and nowhere else, because the server keeps only hashes of
        them. Store them somewhere you can reach without this account.
      </p>
      <ul className="grid grid-cols-2 gap-2 bg-gray-800/50 rounded-lg p-4 font-mono text-sm text-gray-200">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <label className="flex items-center gap-2 text-sm text-gray-300">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
        />
        <span>I have saved these codes somewhere safe.</span>
      </label>
      <Button
        type="button"
        className="w-full"
        disabled={!saved}
        onClick={onDone}
      >
        Done
      </Button>
    </div>
  );
};

/** The one-time code field, shared by the activate, disable and replace legs. */
const CodeField: React.FC<{
  panel: TotpPanel;
  label: string;
  id: string;
  hint: string;
}> = ({ panel, label, id, hint }) => (
  <div>
    <label
      htmlFor={id}
      className="block text-sm font-medium text-foreground mb-2"
    >
      {label}
    </label>
    <Input
      id={id}
      name={id}
      type="text"
      autoComplete="one-time-code"
      inputMode="text"
      value={panel.code}
      onChange={(e) => panel.setCode(e.target.value.slice(0, 32))}
      placeholder="Code"
      disabled={panel.busy}
    />
    <p className="mt-1 text-xs text-gray-400">{hint}</p>
  </div>
);

interface Props {
  /** True when the account already has a factor, from `UserRead.totp_enabled`. */
  enabled: boolean;
  /** Called after a change so the caller can refetch the user. */
  onChanged: () => void;
}

/** The TOTP panel body, mounted only once the identity client could be built. */
const TotpPanelBody: React.FC<Props & { client: IdentityClient }> = ({
  client,
  enabled,
  onChanged,
}) => {
  const [unreachable, setUnreachable] = useState(false);
  const panel = useTotpPanel({
    client,
    factor: enabled ? 'enabled' : 'disabled',
    onChanged,
    messages: {
      disabled: 'Two factor authentication is off.',
      saved: 'Recovery codes saved.',
    },
  });

  const attempt = useCallback((call: () => Promise<void>): void => {
    setUnreachable(false);
    call().catch(() => {
      setUnreachable(true);
    });
  }, []);

  if (panel.step.kind === 'codes') {
    return (
      <RecoveryCodes codes={panel.step.codes} onDone={panel.acknowledgeCodes} />
    );
  }

  const scanning = panel.step.kind === 'scanning' ? panel.step : null;
  const on = panel.factor === 'enabled';

  return (
    <div className="space-y-6">
      {panel.notice !== null && <ConfirmationAlert message={panel.notice} />}
      {panel.error !== null && <ErrorAlert message={panel.error} />}
      {unreachable && <ErrorAlert message={UNREACHABLE} />}

      <div className="flex items-center space-x-3 text-gray-300">
        <FaShieldAlt className="text-primary text-2xl" />
        <div>
          <h3 className="text-lg font-semibold">Two-Factor Authentication</h3>
          <p className="text-sm text-gray-400">
            {enabled
              ? 'Your account asks for a code from your authenticator app when you sign in.'
              : 'Ask for a code from your authenticator app when you sign in.'}
          </p>
        </div>
      </div>

      {scanning !== null && (
        <div className="space-y-4">
          <p className="text-sm text-gray-300">
            Scan this with your authenticator app, then enter the code it shows
            to finish turning it on.
          </p>
          <div className="flex justify-center">
            <ProvisioningQr uri={scanning.provisioningUri} />
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <p className="text-xs text-gray-400 mb-1">
              Cannot scan? Enter this key by hand instead.
            </p>
            <code className="font-mono text-sm text-gray-200 break-all">
              {scanning.secret}
            </code>
          </div>
          <CodeField
            panel={panel}
            label="Code from your app"
            id="totp-activate"
            hint="Six digits, from the app you just scanned into."
          />
          <div className="flex gap-3">
            <Button
              type="button"
              className="flex-1"
              onClick={() => attempt(() => panel.activate())}
              disabled={panel.busy || panel.code.trim() === ''}
              loading={panel.busy}
            >
              Turn on
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              onClick={panel.reset}
              disabled={panel.busy}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {scanning === null && !on && (
        <Button
          type="button"
          className="w-full"
          onClick={() => attempt(() => panel.enrol())}
          disabled={panel.busy}
          loading={panel.busy}
        >
          Set up two-factor authentication
        </Button>
      )}

      {scanning === null && on && (
        <div className="space-y-4">
          <CodeField
            panel={panel}
            label="Current code"
            id="totp-verify"
            hint="A code from your authenticator app, or one of your recovery codes. The current code is the proof, so no password is needed."
          />
          <div className="flex flex-col gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => attempt(() => panel.regenerate())}
              disabled={panel.busy || panel.code.trim() === ''}
            >
              Replace recovery codes
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => attempt(() => panel.disable())}
              disabled={panel.busy || panel.code.trim() === ''}
            >
              Turn off two-factor authentication
            </Button>
          </div>
          <p className="text-xs text-gray-400">
            Replacing recovery codes invalidates every code you were issued
            before.
          </p>
        </div>
      )}
    </div>
  );
};

/** The TOTP panel, or the unavailable notice in bearer mode. */
const IdentityTotpSettings: React.FC<Props> = ({ enabled, onChanged }) => {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <ErrorAlert message="Two factor authentication is not available in this deployment." />
    );
  }
  return (
    <TotpPanelBody client={client} enabled={enabled} onChanged={onChanged} />
  );
};

export default IdentityTotpSettings;
