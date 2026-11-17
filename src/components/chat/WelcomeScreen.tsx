import React from 'react';
import {
  Code,
  ShieldCheck,
  Compass,
  ArrowUpRight,
  Cpu,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { PromptSuggestion } from '../../types';

const SUGGESTED_PROMPTS: PromptSuggestion[] = [
  {
    id: 'p-1',
    category: 'Architecture',
    title: 'FastAPI SSE Streaming',
    prompt: 'How do we design a low-latency SSE streaming endpoint in FastAPI for local Ollama models?',
    icon: 'code',
  },
  {
    id: 'p-2',
    category: 'Local Models',
    title: 'Qwen 3.5 2B Optimization',
    prompt: 'What are the performance advantages and memory footprint of Qwen 3.5 2B in local inference?',
    icon: 'cpu',
  },
  {
    id: 'p-3',
    category: 'Privacy',
    title: 'Zero-Telemetry Design',
    prompt: 'Explain the security and privacy guarantees of running local-first AI with SQLite storage.',
    icon: 'shield',
  },
  {
    id: 'p-4',
    category: 'Desktop App',
    title: 'Tauri 2 Native Packaging',
    prompt: 'How can we structure this React frontend for smooth migration into Tauri 2 for cross-platform desktop?',
    icon: 'compass',
  },
];

export const WelcomeScreen: React.FC<{ onSelectPrompt: (prompt: string) => void }> = ({
  onSelectPrompt,
}) => {
  const { settings, selectedModel } = useApp();

  // Compute greeting based on local time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'code':
        return <Code className="h-4 w-4 text-emerald-400" />;
      case 'cpu':
        return <Cpu className="h-4 w-4 text-cyan-400" />;
      case 'shield':
        return <ShieldCheck className="h-4 w-4 text-indigo-400" />;
      case 'compass':
      default:
        return <Compass className="h-4 w-4 text-amber-400" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-[880px] lg:max-w-[920px] mx-auto select-none animate-fade-in">
      {/* Brand Emblem */}
      <div className="mb-6 relative group">
        <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-moso-accent to-cyan-500 opacity-20 blur-md group-hover:opacity-30 transition duration-300" />
        <div className="relative h-16 w-16 rounded-2xl bg-moso-900 border border-moso-750 flex items-center justify-center p-3 shadow-xl">
          <img src="/logo.svg" alt="Moso AI Logo" className="h-10 w-10" />
        </div>
      </div>

      {/* Greeting & Headline */}
      <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white mb-2">
        {getGreeting()}, {settings.general.username || 'there'}.
      </h1>
      <p className="text-sm text-moso-400 max-w-md mb-8 leading-relaxed">
        Your private, local-first AI assistant. All conversations remain encrypted and stored locally on your device.
      </p>

      {/* Model Status Pill */}
      <div className="mb-8 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-moso-900 border border-moso-800 text-xs text-moso-300">
        <span className="h-2 w-2 rounded-full bg-moso-accent" />
        <span>Ready with model</span>
        <span className="font-mono font-semibold text-white">{selectedModel}</span>
      </div>

      {/* Suggested Prompt Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {SUGGESTED_PROMPTS.map((item) => (
          <div
            key={item.id}
            onClick={() => onSelectPrompt(item.prompt)}
            className="group relative p-4 rounded-xl bg-moso-900/60 hover:bg-moso-850 border border-moso-800/80 hover:border-moso-700/80 transition-all duration-200 cursor-pointer shadow-xs flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded-md bg-moso-800 border border-moso-700/60">
                    {getIcon(item.icon)}
                  </div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-moso-400">
                    {item.category}
                  </span>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-moso-500 group-hover:text-moso-accent transition-colors" />
              </div>
              <h3 className="text-sm font-medium text-white mb-1 group-hover:text-moso-accent transition-colors">
                {item.title}
              </h3>
              <p className="text-xs text-moso-400 line-clamp-2 leading-relaxed">
                {item.prompt}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
