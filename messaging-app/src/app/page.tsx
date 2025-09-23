'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/store/useAppStore';

export default function HomePage() {
  const router = useRouter();
  const { user } = useAppStore();

  useEffect(() => {
    if (user) {
      router.push('/app');
    } else {
      router.push('/signin');
    }
  }, [user, router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}