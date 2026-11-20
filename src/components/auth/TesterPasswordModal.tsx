import React, { useState } from 'react';
import { Lock, KeyRound, Eye, EyeOff, ArrowRight, ShieldCheck, Cpu, Loader2, AlertCircle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { cn } from '../../utils/cn';

export const TesterPasswordModal: React.FC = () => {
  const { isAuthRequired, isAuthenticated, loginWithPassword } = useApp();

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If auth is not required, or the user is already authenticated, don't show the modal
  if (!isAuthRequired || isAuthenticated) {
    return null;
  }

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = password.trim();
    if (!trimmed || isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const success = await loginWithPassword(trimmed);
      if (!success) {
        setErrorMessage('Incorrect tester access password. Please verify with the host.');
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication failed. Please verify with the host.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-moso-950/90 backdrop-blur-md animate-fade-in select-none">
      <div className="relative w-full max-w-md rounded-2xl bg-moso-900 border border-moso-750/90 shadow-2xl p-6 sm:p-8 overflow-hidden">
        {/* Subtle ambient bamboo glow */}
        <div className="absolute -top-16 -right-16 h-40 w-40 rounded-full bg-accent-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-16 -left-16 h-40 w-40 rounded-full bg-moso-accent/10 blur-3xl pointer-events-none" />

        {/* Emblem & Title */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="relative mb-3">
            <div className="h-14 w-14 rounded-2xl bg-moso-850 border border-moso-700/80 flex items-center justify-center p-3 shadow-lg">
              <img src="/logo.svg" alt="Moso AI Logo" className="h-8 w-8" />
            </div>
            <div className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-accent-500 text-moso-950 flex items-center justify-center shadow-xs">
              <Lock className="h-2.5 w-2.5 stroke-[2.5]" />
            </div>
          </div>

          <h2 className="text-xl font-bold tracking-tight text-white">
            Moso AI • Tester Access
          </h2>
          <p className="text-xs text-moso-400 mt-1.5 leading-relaxed max-w-sm">
            This instance is hosted on local hardware and requires a tester password to access AI inference and research workspaces.
          </p>
        </div>

        {/* Error Notification */}
        {errorMessage && (
          <div className="mb-4 flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 animate-fade-in">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
            <span className="leading-snug">{errorMessage}</span>
          </div>
        )}

        {/* Password Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold tracking-wider text-moso-300 uppercase">
              Tester Password
            </label>
            <div className="relative flex items-center">
              <div className="absolute left-3.5 text-moso-500 pointer-events-none">
                <KeyRound className="h-4 w-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                placeholder="Enter access password..."
                autoFocus
                disabled={isLoading}
                className={cn(
                  'w-full bg-moso-850 border rounded-xl pl-10 pr-10 py-2.5 text-sm text-white placeholder:text-moso-500 font-sans transition-all focus:outline-none',
                  errorMessage
                    ? 'border-rose-500/60 focus:border-rose-400 focus:ring-1 focus:ring-rose-400/40'
                    : 'border-moso-700/80 focus:border-moso-accent focus:ring-1 focus:ring-moso-accent/40'
                )}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 text-moso-400 hover:text-white p-1 rounded transition-colors cursor-pointer"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={!password.trim() || isLoading}
            className={cn(
              'w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold transition-all duration-150',
              password.trim() && !isLoading
                ? 'bg-moso-accent text-moso-950 hover:bg-moso-accent-hover shadow-md cursor-pointer'
                : 'bg-moso-800 text-moso-500 cursor-not-allowed border border-moso-750'
            )}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-moso-950" />
                <span>Verifying Access...</span>
              </>
            ) : (
              <>
                <span>Unlock Moso AI</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        {/* Security & Privacy Badges Footer */}
        <div className="mt-6 pt-4 border-t border-moso-800/80 flex flex-wrap items-center justify-between text-[11px] text-moso-500 gap-2">
          <div className="flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-accent-400/90" />
            <span>Local Qwen 3.5 2B CPU</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-accent-400/90" />
            <span>Zero Remote Telemetry</span>
          </div>
        </div>
      </div>
    </div>
  );
};
