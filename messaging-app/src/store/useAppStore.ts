import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UserSettings, User } from '@/types';

interface AppState {
  // User state
  user: User | null;
  setUser: (user: User | null) => void;
  
  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  
  // Command palette
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  
  // Settings
  settings: UserSettings;
  updateSettings: (settings: Partial<UserSettings>) => void;
  
  // Theme
  theme: 'light' | 'dark' | 'system' | 'high-contrast';
  setTheme: (theme: 'light' | 'dark' | 'system' | 'high-contrast') => void;
  
  // Current conversation
  currentConversationId: string | null;
  setCurrentConversationId: (id: string | null) => void;
  
  // Thread drawer
  threadDrawerOpen: boolean;
  setThreadDrawerOpen: (open: boolean) => void;
  currentThreadId: string | null;
  setCurrentThreadId: (id: string | null) => void;
  
  // Search
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  searchFilters: Record<string, any>;
  setSearchFilters: (filters: Record<string, any>) => void;
  
  // Notifications
  notifications: Array<{
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    title: string;
    message?: string;
    duration?: number;
  }>;
  addNotification: (notification: Omit<AppState['notifications'][0], 'id'>) => void;
  removeNotification: (id: string) => void;
  
  // Typing indicators
  typingUsers: Record<string, string[]>; // conversationId -> userIds
  setTypingUsers: (conversationId: string, userIds: string[]) => void;
  
  // Upload progress
  uploadProgress: Record<string, number>; // fileId -> progress
  setUploadProgress: (fileId: string, progress: number) => void;
  removeUploadProgress: (fileId: string) => void;
}

const defaultSettings: UserSettings = {
  theme: 'system',
  fontSize: 'medium',
  reducedMotion: false,
  sendBehavior: 'enter',
  readReceipts: true,
  lastSeen: true,
  notifications: {
    inApp: true,
    browser: false,
    sound: true,
    mentions: true,
    directMessages: true,
    groupMessages: false,
  },
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // User state
      user: null,
      setUser: (user) => set({ user }),
      
      // UI state
      sidebarOpen: true,
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      
      // Command palette
      commandPaletteOpen: false,
      setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
      
      // Settings
      settings: defaultSettings,
      updateSettings: (newSettings) =>
        set((state) => ({
          settings: { ...state.settings, ...newSettings },
        })),
      
      // Theme
      theme: 'system',
      setTheme: (theme) => {
        set({ theme });
        get().updateSettings({ theme });
      },
      
      // Current conversation
      currentConversationId: null,
      setCurrentConversationId: (currentConversationId) => set({ currentConversationId }),
      
      // Thread drawer
      threadDrawerOpen: false,
      setThreadDrawerOpen: (threadDrawerOpen) => set({ threadDrawerOpen }),
      currentThreadId: null,
      setCurrentThreadId: (currentThreadId) => set({ currentThreadId }),
      
      // Search
      searchQuery: '',
      setSearchQuery: (searchQuery) => set({ searchQuery }),
      searchFilters: {},
      setSearchFilters: (searchFilters) => set({ searchFilters }),
      
      // Notifications
      notifications: [],
      addNotification: (notification) =>
        set((state) => ({
          notifications: [
            ...state.notifications,
            { ...notification, id: Math.random().toString(36).substr(2, 9) },
          ],
        })),
      removeNotification: (id) =>
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        })),
      
      // Typing indicators
      typingUsers: {},
      setTypingUsers: (conversationId, userIds) =>
        set((state) => ({
          typingUsers: {
            ...state.typingUsers,
            [conversationId]: userIds,
          },
        })),
      
      // Upload progress
      uploadProgress: {},
      setUploadProgress: (fileId, progress) =>
        set((state) => ({
          uploadProgress: {
            ...state.uploadProgress,
            [fileId]: progress,
          },
        })),
      removeUploadProgress: (fileId) =>
        set((state) => {
          const { [fileId]: _, ...rest } = state.uploadProgress;
          return { uploadProgress: rest };
        }),
    }),
    {
      name: 'messaging-app-storage',
      partialize: (state) => ({
        settings: state.settings,
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
);
