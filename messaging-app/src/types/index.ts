export interface User {
  id: string;
  email: string;
  displayName: string;
  handle: string;
  avatar?: string;
  bio?: string;
  status: 'online' | 'away' | 'offline' | 'dnd';
  lastSeen?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Attachment {
  id: string;
  messageId: string;
  type: 'image' | 'file' | 'video' | 'audio';
  name: string;
  url: string;
  size: number;
  mimeType: string;
  thumbnailUrl?: string;
  createdAt: string;
}

export interface Reaction {
  id: string;
  messageId: string;
  userId: string;
  emoji: string;
  createdAt: string;
}

export interface Message {
  id: string;
  conversationId: string;
  userId: string;
  content: string;
  type: 'text' | 'system' | 'file';
  status: 'sending' | 'sent' | 'delivered' | 'read' | 'failed';
  editedAt?: string;
  replyToId?: string;
  threadId?: string;
  attachments: Attachment[];
  reactions: Reaction[];
  mentions: string[];
  isPinned: boolean;
  isStarred: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Conversation {
  id: string;
  name: string;
  type: 'dm' | 'group' | 'channel';
  description?: string;
  avatar?: string;
  participants: string[];
  lastMessage?: Message;
  unreadCount: number;
  isPinned: boolean;
  isMuted: boolean;
  isArchived: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SearchResult {
  type: 'message' | 'conversation' | 'user';
  id: string;
  title: string;
  content?: string;
  conversationId?: string;
  conversationName?: string;
  timestamp?: string;
  highlights?: string[];
}

export interface SearchFilters {
  hasUnread?: boolean;
  hasAttachments?: boolean;
  mentionsMe?: boolean;
  isStarred?: boolean;
  authorId?: string;
  dateFrom?: string;
  dateTo?: string;
  conversationType?: 'dm' | 'group' | 'channel';
}

export interface NotificationSettings {
  inApp: boolean;
  browser: boolean;
  sound: boolean;
  mentions: boolean;
  directMessages: boolean;
  groupMessages: boolean;
}

export interface UserSettings {
  theme: 'light' | 'dark' | 'system' | 'high-contrast';
  fontSize: 'small' | 'medium' | 'large';
  reducedMotion: boolean;
  sendBehavior: 'enter' | 'shift-enter';
  readReceipts: boolean;
  lastSeen: boolean;
  notifications: NotificationSettings;
}

export interface Thread {
  id: string;
  messageId: string;
  conversationId: string;
  messages: Message[];
  participantCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Presence {
  userId: string;
  status: 'online' | 'away' | 'offline' | 'dnd';
  lastSeen: string;
}

export interface TypingIndicator {
  conversationId: string;
  userId: string;
  timestamp: string;
}

export interface CommandPaletteItem {
  id: string;
  type: 'conversation' | 'user' | 'action';
  title: string;
  subtitle?: string;
  icon?: string;
  action: () => void;
}

export interface UploadProgress {
  fileId: string;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
}

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    hasMore: boolean;
  };
}
