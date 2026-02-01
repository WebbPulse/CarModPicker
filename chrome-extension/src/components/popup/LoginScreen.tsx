import type { FormEvent } from "react";
import React, { useState } from "react";
import type { ApiResponse, User } from "../../types";

interface LoginScreenProps {
  onLogin: (user: User) => void;
  sendMessage: (message: {
    action: string;
    username?: string;
    password?: string;
    otp?: string;
  }) => Promise<unknown>;
}

const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin, sendMessage }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [requires2FA, setRequires2FA] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      if (requires2FA) {
        // Complete login with OTP
        if (!otp.trim() || otp.length !== 6) {
          setError("Please enter a valid 6-digit OTP code.");
          setIsLoading(false);
          return;
        }

        const response = (await sendMessage({
          action: "loginWith2FA",
          username,
          password,
          otp,
        })) as ApiResponse<User>;

        if (response.success && response.data) {
          onLogin(response.data);
        } else {
          setError(response.error || "Invalid OTP code");
        }
      } else {
        // Initial login with username/password
        const response = (await sendMessage({
          action: "login",
          username,
          password,
        })) as ApiResponse<User> & { requires2FA?: boolean };

        if (response.success && response.data) {
          onLogin(response.data);
        } else if (response.requires2FA) {
          setRequires2FA(true);
          setError("");
        } else {
          setError(response.error || "Login failed");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSettingsClick = (e: React.MouseEvent) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  };

  return (
    <div className="p-5">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gradient mb-2">CarModPicker</h1>
        <p className="text-neutral-400 text-sm">
          {requires2FA ? "Two-Factor Authentication" : "Part Scraper"}
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {!requires2FA ? (
          <>
            <div>
              <label
                htmlFor="username"
                className="block text-sm font-medium text-neutral-300 mb-2"
              >
                Username
              </label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-neutral-300 mb-2"
              >
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>
          </>
        ) : (
          <>
            <div>
              <label
                htmlFor="otp"
                className="block text-sm font-medium text-neutral-300 mb-2"
              >
                Authentication Code
              </label>
              <input
                type="text"
                id="otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, "").slice(0, 6);
                  setOtp(value);
                }}
                placeholder="000000"
                maxLength={6}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
              <p className="mt-2 text-xs text-neutral-400">
                Enter the 6-digit code from your authenticator app
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setRequires2FA(false);
                setOtp("");
                setError("");
              }}
              className="text-sm text-primary-400 hover:text-primary-300 transition-colors w-full text-center"
            >
              ← Back to login
            </button>
          </>
        )}

        <button
          type="submit"
          className="w-full py-3 px-6 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          disabled={isLoading}
        >
          {isLoading ? "Logging in..." : requires2FA ? "Verify" : "Login"}
        </button>
      </form>

      <div className="mt-6 text-center">
        <a
          href="#"
          onClick={handleSettingsClick}
          className="text-primary-400 text-sm hover:text-primary-300 transition-colors"
        >
          Settings
        </a>
      </div>
    </div>
  );
};

export default LoginScreen;
