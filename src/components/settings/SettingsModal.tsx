import React, { useState } from 'react';
import {
  Settings as SettingsIcon,
  Palette,
  Sliders,
  Server,
  Shield,
  Info,
  RefreshCw,
  Trash2,
  Lock,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { cn } from '../../utils/cn';

type SettingsTab = 'general' | 'appearance' | 'models' | 'localAi' | 'privacy' | 'about';

export const SettingsModal: React.FC = () => {
  const {
    isSettingsOpen,
    closeSettings,
    settings,
    updateSettings,
    availableModels,
    checkConnection,
    connectionState,
    healthInfo,
    isMockMode,
    toggleMockMode,
    clearAllHistory,
    isAuthRequired,
    isAuthenticated,
    logoutSession,
  } = useApp();

  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  if (!isSettingsOpen) return null;

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestResult(null);
    try {
      await checkConnection();
      if (isMockMode) {
        setTestResult({
          success: true,
          message: 'Connected to Dev Mock Simulator (12ms latency).',
        });
      } else {
        setTestResult({
          success: connectionState === 'connected',
          message:
            connectionState === 'connected'
              ? `Connected to FastAPI & Ollama successfully (${healthInfo?.latency_ms || 15}ms).`
              : 'Could not reach local FastAPI server. Ensure uvicorn is running on port 8000.',
        });
      }
    } catch (e: any) {
      setTestResult({
        success: false,
        message: 'Connection failed: ' + (e.message || 'Network error'),
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const navItems: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
    { id: 'general', label: 'General', icon: <SettingsIcon className="h-4 w-4" /> },
    { id: 'appearance', label: 'Appearance', icon: <Palette className="h-4 w-4" /> },
    { id: 'models', label: 'Models', icon: <Sliders className="h-4 w-4" /> },
    { id: 'localAi', label: 'Local AI', icon: <Server className="h-4 w-4" /> },
    { id: 'privacy', label: 'Privacy', icon: <Shield className="h-4 w-4" /> },
    { id: 'about', label: 'About Moso AI', icon: <Info className="h-4 w-4" /> },
  ];

  return (
    <Modal
      isOpen={isSettingsOpen}
      onClose={closeSettings}
      maxWidth="2xl"
      className="h-[620px]"
      title={
        <div className="flex items-center gap-2">
          <SettingsIcon className="h-5 w-5 text-moso-accent" />
          <span className="text-lg font-semibold text-white">Settings</span>
        </div>
      }
    >
      <div className="flex h-full gap-6">
        {/* Sidebar Tabs */}
        <div className="w-48 shrink-0 flex flex-col space-y-1 border-r border-moso-800/80 pr-4">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                'flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left cursor-pointer',
                activeTab === item.id
                  ? 'bg-moso-800 text-white font-semibold'
                  : 'text-moso-400 hover:text-white hover:bg-moso-850'
              )}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}

          {/* Dev Mock Switch shortcut in settings */}
          <div className="pt-6 mt-auto border-t border-moso-800/80">
            <div className="p-2.5 rounded-lg bg-moso-950/80 border border-moso-800 text-[11px]">
              <span className="font-semibold text-moso-300 block mb-1">Backend Mode</span>
              <button
                type="button"
                onClick={toggleMockMode}
                className={cn(
                  'w-full py-1 px-2 rounded text-[10px] font-mono font-medium border text-center transition-colors',
                  isMockMode
                    ? 'bg-cyan-500/15 border-cyan-500/30 text-cyan-300'
                    : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                )}
              >
                {isMockMode ? 'Dev Mock Mode (Active)' : 'Live Backend (Active)'}
              </button>
            </div>
          </div>
        </div>

        {/* Tab Content Panes */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-6 text-xs text-moso-300">
          {/* GENERAL TAB */}
          {activeTab === 'general' && (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-white mb-1">User Profile</h4>
                <p className="text-moso-400 text-xs mb-2">Used for personalised greetings and context.</p>
                <Input
                  value={settings.general.username}
                  onChange={(e) => updateSettings({ general: { ...settings.general, username: e.target.value } })}
                  placeholder="Your Name"
                />
              </div>

              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Default System Instructions</h4>
                <p className="text-moso-400 text-xs mb-2">Injected into conversation prompts.</p>
                <textarea
                  rows={3}
                  value={settings.general.systemPrompt}
                  onChange={(e) => updateSettings({ general: { ...settings.general, systemPrompt: e.target.value } })}
                  className="w-full bg-moso-900 border border-moso-700/70 rounded-lg p-2.5 text-xs text-moso-100 placeholder:text-moso-500 focus:outline-none focus:border-moso-accent"
                />
              </div>

              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Send Key Behavior</h4>
                <div className="flex gap-3 mt-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={settings.general.sendShortcut === 'enter'}
                      onChange={() => updateSettings({ general: { ...settings.general, sendShortcut: 'enter' } })}
                      className="accent-moso-accent"
                    />
                    <span>Enter to send, Shift + Enter for newline</span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* APPEARANCE TAB */}
          {activeTab === 'appearance' && (
            <div className="space-y-5">
              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Interface Theme</h4>
                <p className="text-moso-400 text-xs mb-3">Moso AI defaults to dark themes optimized for focus.</p>
                <div className="grid grid-cols-3 gap-2.5">
                  {[
                    { id: 'dark', label: 'Dark Obsidian (Default)' },
                    { id: 'oled', label: 'Midnight OLED' },
                    { id: 'zinc', label: 'Titanium Zinc' },
                  ].map((t) => (
                    <button
                      key={t.id}
                      onClick={() => updateSettings({ appearance: { ...settings.appearance, theme: t.id as any } })}
                      className={cn(
                        'p-3 rounded-lg border text-left transition-colors cursor-pointer',
                        settings.appearance.theme === t.id
                          ? 'border-moso-accent bg-moso-800 text-white font-medium'
                          : 'border-moso-750 bg-moso-900 text-moso-400 hover:border-moso-700'
                      )}
                    >
                      <span className="block text-xs">{t.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Chat Font Size</h4>
                <div className="flex gap-2 mt-2">
                  {(['small', 'medium', 'large'] as const).map((size) => (
                    <Button
                      key={size}
                      variant={settings.appearance.fontSize === size ? 'primary' : 'secondary'}
                      size="sm"
                      onClick={() => updateSettings({ appearance: { ...settings.appearance, fontSize: size } })}
                      className="capitalize"
                    >
                      {size}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-moso-800">
                <label className="flex items-center justify-between cursor-pointer py-1">
                  <div>
                    <span className="text-white font-medium block">Show Message Timestamps</span>
                    <span className="text-moso-400 text-[11px]">Display time sent below each message</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.appearance.showTimestamps}
                    onChange={(e) =>
                      updateSettings({ appearance: { ...settings.appearance, showTimestamps: e.target.checked } })
                    }
                    className="accent-moso-accent h-4 w-4"
                  />
                </label>
              </div>
            </div>
          )}

          {/* MODELS TAB */}
          {activeTab === 'models' && (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Default Model</h4>
                <p className="text-moso-400 text-xs mb-2">Selected model for new sessions.</p>
                <select
                  value={settings.models.defaultModel}
                  onChange={(e) => updateSettings({ models: { ...settings.models, defaultModel: e.target.value } })}
                  className="w-full bg-moso-900 border border-moso-700 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-moso-accent"
                >
                  {availableModels
                    .filter((m) => m.is_local)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.size})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-sm font-semibold text-white">Temperature: {settings.models.temperature}</h4>
                  <span className="text-moso-500 font-mono text-[11px]">0.0 - 1.0</span>
                </div>
                <p className="text-moso-400 text-xs mb-2">Lower is more deterministic; higher is more creative.</p>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.models.temperature}
                  onChange={(e) =>
                    updateSettings({ models: { ...settings.models, temperature: parseFloat(e.target.value) } })
                  }
                  className="w-full accent-moso-accent"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-sm font-semibold text-white">Max Response Tokens: {settings.models.maxTokens}</h4>
                  <span className="text-moso-500 font-mono text-[11px]">tokens</span>
                </div>
                <p className="text-moso-400 text-xs mb-2">Recommended ~256 for fast CPU generation on Intel Core i5 laptops.</p>
                <input
                  type="range"
                  min="64"
                  max="4096"
                  step="64"
                  value={settings.models.maxTokens}
                  onChange={(e) =>
                    updateSettings({ models: { ...settings.models, maxTokens: parseInt(e.target.value, 10) } })
                  }
                  className="w-full accent-moso-accent"
                />
              </div>

              {/* Cloud Provider Placeholder */}
              <div className="p-3.5 rounded-xl bg-moso-950 border border-dashed border-moso-800 text-moso-400 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-moso-300">Cloud Model Connectors</span>
                  <Badge variant="muted" size="sm">Planned Future</Badge>
                </div>
                <p className="text-[11px] text-moso-500">
                  Support for external API keys (OpenAI, Anthropic, OpenRouter) with hybrid fallbacks will be available in future releases.
                </p>
              </div>
            </div>
          )}

          {/* LOCAL AI TAB */}
          {activeTab === 'localAi' && (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-white mb-1">FastAPI Backend Endpoint</h4>
                <p className="text-moso-400 text-xs mb-2">Base URL for Moso AI backend server.</p>
                <Input
                  value={settings.localAi.apiEndpoint}
                  onChange={(e) => updateSettings({ localAi: { ...settings.localAi, apiEndpoint: e.target.value } })}
                  placeholder="/api/v1 or http://localhost:8000/api/v1"
                />
              </div>

              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Local Ollama Endpoint</h4>
                <p className="text-moso-400 text-xs mb-2">Direct Ollama inference API endpoint.</p>
                <Input
                  value={settings.localAi.ollamaEndpoint}
                  onChange={(e) =>
                    updateSettings({ localAi: { ...settings.localAi, ollamaEndpoint: e.target.value } })
                  }
                  placeholder="http://localhost:11434"
                />
              </div>

              <div className="pt-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleTestConnection}
                  isLoading={testingConnection}
                  className="gap-2"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>Test Connection</span>
                </Button>

                {testResult && (
                  <div
                    className={cn(
                      'mt-3 p-3 rounded-lg border text-xs leading-relaxed',
                      testResult.success
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                        : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                    )}
                  >
                    <p className="font-semibold">{testResult.success ? 'Online' : 'Unreachable'}</p>
                    <p className="mt-0.5">{testResult.message}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PRIVACY TAB */}
          {activeTab === 'privacy' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-moso-900 border border-emerald-500/20 space-y-2">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                  <Shield className="h-4 w-4" />
                  <span>Zero-Telemetry Commitment</span>
                </div>
                <p className="text-xs text-moso-300 leading-relaxed">
                  Moso AI is designed from first principles to be local-first. Prompts, completions, embeddings, and chat histories are processed exclusively on your machine. No analytics, tracking, or cloud telemetries are included.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-moso-850/60 border border-moso-750 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-moso-400">Current Storage Backend:</span>
                  <Badge variant={isMockMode ? 'warning' : 'success'} size="sm">
                    {isMockMode ? 'Browser LocalStorage (Mock Mode)' : 'Local SQLite (backend/moso.db)'}
                  </Badge>
                </div>
                <p className="text-[11px] text-moso-400 leading-relaxed">
                  {isMockMode
                    ? 'Dev Mock Mode is active. Data is simulated and stored inside your browser localStorage.'
                    : 'Real Backend Mode is active. All user prompts and assistant completions are persistently saved to your local SQLite database.'}
                </p>
              </div>

              {/* Public Port Forwarding & Remote Tester Protection */}
              <div className="p-3.5 rounded-xl bg-moso-850/60 border border-moso-750 text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-medium text-white">
                    <Lock className="h-3.5 w-3.5 text-moso-accent" />
                    <span>Public Port Forwarding Protection</span>
                  </div>
                  <Badge variant={isAuthRequired ? 'success' : 'muted'} size="sm">
                    {isAuthRequired ? 'Password Protected' : 'Open Access'}
                  </Badge>
                </div>
                <p className="text-[11px] text-moso-400 leading-relaxed">
                  {isAuthRequired
                    ? 'MOSO_ACCESS_PASSWORD is active on the server. Remote testers must provide the password before accessing chat, document ingestion, or projects.'
                    : 'No access password set on backend. To password-protect remote forwarded ports, set MOSO_ACCESS_PASSWORD in your .env file or environment.'}
                </p>
                {isAuthRequired && isAuthenticated && (
                  <div className="pt-1">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={async () => {
                        await logoutSession();
                        closeSettings();
                      }}
                      className="gap-1.5 text-amber-400 hover:text-amber-300"
                    >
                      <Lock className="h-3.5 w-3.5" />
                      <span>Lock Tester Session Now</span>
                    </Button>
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-moso-800">
                <h4 className="text-sm font-semibold text-white mb-1">Local Storage Management</h4>
                <p className="text-moso-400 text-xs mb-3">
                  {isMockMode
                    ? 'Clear mock conversation history stored in your browser.'
                    : 'Clear conversation history and messages from your local SQLite database.'}
                </p>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => setShowClearConfirm(true)}
                  className="gap-1.5"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Clear All Conversations</span>
                </Button>
              </div>
            </div>
          )}

          {/* ABOUT TAB */}
          {activeTab === 'about' && (
            <div className="space-y-4 select-none">
              <div className="flex items-center gap-3">
                <img src="/logo.svg" alt="Moso AI" className="h-10 w-10 rounded-xl shadow-md" />
                <div>
                  <h3 className="text-base font-semibold text-white">Moso AI</h3>
                  <p className="text-xs text-moso-400">Version 0.1.0 • Local-First Personal AI</p>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-moso-800 text-xs">
                <div className="flex justify-between py-1 border-b border-moso-800/60">
                  <span className="text-moso-400">Frontend Stack</span>
                  <span className="text-moso-200 font-medium">React 18 • TypeScript • Vite • Tailwind</span>
                </div>
                <div className="flex justify-between py-1 border-b border-moso-800/60">
                  <span className="text-moso-400">Desktop Shell Target</span>
                  <span className="text-moso-200 font-medium">Tauri 2 (Rust)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-moso-800/60">
                  <span className="text-moso-400">Backend API</span>
                  <span className="text-moso-200 font-medium">FastAPI & SSE Streaming</span>
                </div>
                <div className="flex justify-between py-1 border-b border-moso-800/60">
                  <span className="text-moso-400">Local Inference Engine</span>
                  <span className="text-moso-200 font-medium">Ollama (Qwen 3.5 2B)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-moso-800/60">
                  <span className="text-moso-400">Data Storage</span>
                  <span className="text-moso-200 font-medium">SQLite (Zero Telemetry)</span>
                </div>
              </div>

              {/* Placeholder for future features */}
              <div className="pt-2">
                <span className="text-[11px] font-semibold text-moso-400 uppercase tracking-wider block mb-2">
                  Roadmap & Extensions
                </span>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-moso-850 border border-moso-750 text-moso-400 flex items-center justify-between">
                    <span>Multimodal Vision</span>
                    <Badge variant="muted" size="sm">Planned</Badge>
                  </div>
                  <div className="p-2 rounded bg-moso-850 border border-moso-750 text-moso-400 flex items-center justify-between">
                    <span>Voice Input / STT</span>
                    <Badge variant="muted" size="sm">Planned</Badge>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Clear Confirmation Sub-Modal */}
      <Modal
        isOpen={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        title="Clear all conversations?"
        description="This will permanently delete all conversation records from your local storage. This action cannot be reversed."
        maxWidth="sm"
      >
        <div className="flex justify-end gap-2.5 pt-3">
          <Button variant="ghost" onClick={() => setShowClearConfirm(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              await clearAllHistory();
              setShowClearConfirm(false);
              closeSettings();
            }}
          >
            Clear Everything
          </Button>
        </div>
      </Modal>
    </Modal>
  );
};
