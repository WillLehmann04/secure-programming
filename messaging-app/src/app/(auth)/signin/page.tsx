'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';
import { apiClient, ApiError } from '@/services/api';

const signInSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

type SignInForm = z.infer<typeof signInSchema>;

export default function SignInPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isMagicLink, setIsMagicLink] = useState(false);
  const router = useRouter();
  const { setUser } = useAppStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInForm>({
    resolver: zodResolver(signInSchema),
  });

  const onSubmit = async (data: SignInForm) => {
    setIsLoading(true);
    try {
      const response = await apiClient.signIn(data.email, data.password);

      if (response.success) {
        setUser(response.user);
        router.push('/');
      } else {
        console.error('Sign in failed:', response.message);
      }
    } catch (error) {
      if (error instanceof ApiError) {
        console.error('Sign in error:', error.message);
      } else {
        console.error('Sign in error:', error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleMagicLink = async (data: { email: string }) => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/auth/magic-link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      if (result.success) {
        setIsMagicLink(true);
      }
    } catch (error) {
      console.error('Magic link error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isMagicLink) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="max-w-md w-full space-y-8 p-8">
          <div className="text-center">
            <h2 className="mt-6 text-3xl font-bold text-foreground">
              Check your email
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              We've sent you a magic link to sign in.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-bold text-foreground">
            Sign in to your account
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Or use magic link for passwordless sign in
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="sr-only">
                Email address
              </label>
              <Input
                id="email"
                type="email"
                placeholder="Email address"
                {...register('email')}
                className={errors.email ? 'border-destructive' : ''}
              />
              {errors.email && (
                <p className="mt-1 text-sm text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Password"
                {...register('password')}
                className={errors.password ? 'border-destructive' : ''}
              />
              {errors.password && (
                <p className="mt-1 text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>

            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => {
                const email = (document.getElementById('email') as HTMLInputElement)?.value;
                if (email) {
                  handleMagicLink({ email });
                }
              }}
              disabled={isLoading}
            >
              Send magic link
            </Button>
          </div>

          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              Demo credentials: alice@example.com / password
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
