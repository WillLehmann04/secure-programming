import { test, expect } from '@playwright/test';

test.describe('Sign In', () => {
  test('should sign in with valid credentials', async ({ page }) => {
    await page.goto('/signin');
    
    await page.fill('input[type="email"]', 'alice@example.com');
    await page.fill('input[type="password"]', 'password');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/app');
    await expect(page.locator('text=Messages')).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/signin');
    
    await page.fill('input[type="email"]', 'invalid@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    // Should stay on signin page
    await expect(page).toHaveURL('/signin');
  });

  test('should show magic link option', async ({ page }) => {
    await page.goto('/signin');
    
    await page.fill('input[type="email"]', 'alice@example.com');
    await page.click('text=Send magic link');
    
    await expect(page.locator('text=Check your email')).toBeVisible();
  });
});
