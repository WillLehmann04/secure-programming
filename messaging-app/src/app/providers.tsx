'use client';

import { useEffect, useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [mswReady, setMswReady] = useState(false);

  useEffect(() => {
    const initMsw = async () => {
      if (process.env.NODE_ENV === 'development') {
        const { worker } = await import('@/mocks/browser');
        await worker.start();
      }
      setMswReady(true);
    };

    initMsw();
  }, []);

  if (!mswReady) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return <>{children}</>;
}
