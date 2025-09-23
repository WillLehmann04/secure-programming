import createMiddleware from 'next-intl/middleware';

export default createMiddleware({
  locales: ['en-AU', 'ar'],
  defaultLocale: 'en-AU',
  localeDetection: true,
});

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)']
};
