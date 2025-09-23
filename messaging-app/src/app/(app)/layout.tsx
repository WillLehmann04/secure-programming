'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from '@/store/useAppStore';
import { Sidebar } from '@/components/navigation/Sidebar';
import { CommandPalette } from '@/components/CommandPalette';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, sidebarOpen } = useAppStore();

  useEffect(() => {
    if (!user) {
      router.push('/signin');
    }
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-background">
        {/* Sidebar */}
        <div
          className={`${
            sidebarOpen ? 'w-80' : 'w-0'
          } transition-all duration-300 ease-in-out overflow-hidden`}
        >
          <Sidebar />
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0">
          {children}
        </div>

        {/* Command Palette */}
        <CommandPalette />
      </div>
    </QueryClientProvider>
  );
}
