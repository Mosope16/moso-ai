import React from 'react';
import { Code, ShieldCheck, Compass, Cpu } from 'lucide-react';
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

interface WelcomeScreenProps {
  onSelectPrompt: (prompt: string) => void;
  /** The composer, shown directly under the greeting. */
  children?: React.ReactNode;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSelectPrompt, children }) => {
  const { settings } = useApp();

  // Greeting follows the local clock
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const getIcon = (iconName: string) => {
    const cls = 'h-4 w-4 text-moso-400 group-hover:text-moso-accent transition-colors';
    switch (iconName) {
      case 'code':
        return <Code className={cls} />;
      case 'cpu':
        return <Cpu className={cls} />;
      case 'shield':
        return <ShieldCheck className={cls} />;
      case 'compass':
      default:
        return <Compass className={cls} />;
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-1 pb-8 sm:pb-14 text-center w-full max-w-[760px] mx-auto animate-fade-in">
      <div className="flex items-center justify-center gap-3 sm:gap-4 mb-6 sm:mb-9">
        <img src="/logo.svg" alt="" className="h-9 w-9 sm:h-11 sm:w-11 shrink-0" />
        <h1 className="font-serif text-[28px] sm:text-[40px] leading-[1.15] tracking-tight text-white text-left">
          {getGreeting()}, {settings.general.username || 'there'}
        </h1>
      </div>

      {children}

      <div className="mt-5 flex flex-wrap justify-center gap-2 select-none">
        {SUGGESTED_PROMPTS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelectPrompt(item.prompt)}
            title={item.prompt}
            className="group inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border border-moso-750 text-[13.5px] text-moso-300 hover:text-white hover:bg-moso-800/60 transition-colors cursor-pointer"
          >
            {getIcon(item.icon)}
            <span>{item.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
