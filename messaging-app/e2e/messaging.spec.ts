import { test, expect } from '@playwright/test';

test.describe('Messaging', () => {
  test.beforeEach(async ({ page }) => {
    // Sign in first
    await page.goto('/signin');
    await page.fill('input[type="email"]', 'alice@example.com');
    await page.fill('input[type="password"]', 'password');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/app');
  });

  test('should send a message', async ({ page }) => {
    // Click on first conversation
    await page.click('[data-testid="conversation-item"]:first-child');
    
    // Type message
    await page.fill('textarea[placeholder="Type a message..."]', 'Hello, world!');
    await page.click('button[type="submit"]');
    
    // Message should appear
    await expect(page.locator('text=Hello, world!')).toBeVisible();
  });

  test('should open command palette', async ({ page }) => {
    await page.keyboard.press('Meta+k');
    await expect(page.locator('text=Search conversations, users, or commands...')).toBeVisible();
    
    await page.keyboard.press('Escape');
    await expect(page.locator('text=Search conversations, users, or commands...')).not.toBeVisible();
  });

  test('should search conversations', async ({ page }) => {
    await page.fill('input[placeholder="Search conversations..."]', 'General');
    await expect(page.locator('text=General')).toBeVisible();
  });

  test('should show message actions on hover', async ({ page }) => {
    await page.click('[data-testid="conversation-item"]:first-child');
    
    // Hover over a message
    await page.hover('[data-testid="message-item"]:first-child');
    
    await expect(page.locator('text=Reply')).toBeVisible();
    await expect(page.locator('text=Edit')).toBeVisible();
    await expect(page.locator('text=Copy')).toBeVisible();
  });
});
