export type DateGroup = 'Today' | 'Yesterday' | 'Previous 7 Days' | 'Previous 30 Days' | 'Older';

export interface GroupedItems<T> {
  Today: T[];
  Yesterday: T[];
  'Previous 7 Days': T[];
  'Previous 30 Days': T[];
  Older: T[];
}

export function groupConversationsByDate<T extends { updated_at?: string; created_at?: string }>(
  items: T[]
): Record<DateGroup, T[]> {
  const groups: Record<DateGroup, T[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 Days': [],
    'Previous 30 Days': [],
    Older: [],
  };

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const oneDayMs = 24 * 60 * 60 * 1000;
  const startOfYesterday = startOfToday - oneDayMs;
  const startOf7Days = startOfToday - 7 * oneDayMs;
  const startOf30Days = startOfToday - 30 * oneDayMs;

  for (const item of items) {
    const rawDate = item.updated_at || item.created_at || new Date().toISOString();
    const itemTime = new Date(rawDate).getTime();

    if (itemTime >= startOfToday) {
      groups['Today'].push(item);
    } else if (itemTime >= startOfYesterday) {
      groups['Yesterday'].push(item);
    } else if (itemTime >= startOf7Days) {
      groups['Previous 7 Days'].push(item);
    } else if (itemTime >= startOf30Days) {
      groups['Previous 30 Days'].push(item);
    } else {
      groups['Older'].push(item);
    }
  }

  return groups;
}

export function formatMessageTime(isoString?: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return '';
  
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelativeTime(isoString?: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return '';
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDays = Math.floor(diffHour / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
