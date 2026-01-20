import React, { useState } from 'react';
import { FaEye, FaEyeSlash, FaLock, FaShieldAlt, FaUser } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link, useNavigate } from 'react-router-dom';
import Button from '../../components/buttons/Button';
import Input from '../../components/common/Input';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { authApi } from '../../services/Api';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [requires2FA, setRequires2FA] = useState(false);
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();

  const loginRequestFn = (payload: URLSearchParams) =>
    authApi.login(payload as unknown as { username: string; password: string });

  const {
    error: apiError,
    isLoading,
    executeRequest: performLogin,
    setError: setApiError,
  } = useApiRequest(loginRequestFn);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (!username.trim() || !password.trim()) {
      setApiError('Username and password cannot be empty.');
      return;
    }

    // If 2FA is required, handle OTP verification
    if (requires2FA) {
      if (!otp.trim() || otp.length !== 6) {
        setApiError('Please enter a valid 6-digit OTP code.');
        return;
      }

      try {
        const result = await authApi.loginWith2FA({
          username,
          password,
          otp,
        });
        if (result.data) {
          authLogin(result.data);
          void navigate('/');
        }
      } catch (error: unknown) {
        const axiosError = error as {
          response?: { data?: { detail?: string } };
        };
        setApiError(
          axiosError.response?.data?.detail ||
            'Invalid OTP code. Please try again.'
        );
      }
      return;
    }

    // Regular login
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const result = await performLogin(formData);
      // Check if result is a LoginResponse with requires_2fa
      if (result && 'requires_2fa' in result && result.requires_2fa) {
        setRequires2FA(true);
        setApiError(null);
      } else if (result && 'id' in result) {
        // Regular login success
        authLogin(result);
        void navigate('/');
      }
    } catch {
      // Login failed - error is handled by useApiRequest
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl animate-float"></div>
        <div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl animate-float"
          style={{ animationDelay: '1s' }}
        ></div>
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="glass-card rounded-2xl p-8 animate-slideInUp">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center shadow-lg">
                <GiRaceCar className="text-white text-2xl" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white mb-2">
              {requires2FA ? 'Two-Factor Authentication' : 'Welcome Back'}
            </h2>
            <p className="text-neutral-400">
              {requires2FA
                ? 'Enter the 6-digit code from your authenticator app'
                : 'Sign in to your CarModPicker account'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
            {!requires2FA ? (
              <>
                <Input
                  label="Username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  disabled={isLoading}
                  leftIcon={<FaUser />}
                  variant="glass"
                />

                <Input
                  label="Password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  disabled={isLoading}
                  leftIcon={<FaLock />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-neutral-400 hover:text-white transition-colors"
                    >
                      {showPassword ? <FaEyeSlash /> : <FaEye />}
                    </button>
                  }
                  variant="glass"
                />
              </>
            ) : (
              <>
                <div className="flex justify-center mb-4">
                  <div className="w-20 h-20 bg-primary-500/20 rounded-full flex items-center justify-center">
                    <FaShieldAlt className="text-primary-400 text-3xl" />
                  </div>
                </div>
                <Input
                  label="Authentication Code"
                  name="otp"
                  type="text"
                  autoComplete="one-time-code"
                  required
                  value={otp}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                    setOtp(value);
                  }}
                  placeholder="000000"
                  disabled={isLoading}
                  leftIcon={<FaShieldAlt />}
                  variant="glass"
                  maxLength={6}
                />
                <button
                  type="button"
                  onClick={() => {
                    setRequires2FA(false);
                    setOtp('');
                    setApiError(null);
                  }}
                  className="text-sm text-primary-400 hover:text-primary-300 transition-colors duration-300 w-full text-center"
                >
                  ← Back to login
                </button>
              </>
            )}

            {apiError && (
              <div className="animate-slideInUp">
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                  <p className="text-red-400 text-sm">{apiError}</p>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Link
                to="/forgot-password"
                className="text-sm text-primary-400 hover:text-primary-300 transition-colors duration-300"
              >
                Forgot your password?
              </Link>
            </div>

            <Button
              type="submit"
              loading={isLoading}
              disabled={isLoading}
              className="w-full"
              size="lg"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-neutral-400 text-sm">
              Don't have an account?{' '}
              <Link
                to="/register"
                className="text-primary-400 hover:text-primary-300 font-semibold transition-colors duration-300"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-neutral-500 text-xs">
            By signing in, you agree to our{' '}
            <Link
              to="/privacy-policy"
              className="text-neutral-400 hover:text-white transition-colors"
            >
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
