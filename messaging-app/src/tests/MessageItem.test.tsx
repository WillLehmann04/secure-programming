import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MessageItem } from '@/components/chat/MessageItem';
import { Message } from '@/types';

const mockMessage: Message = {
  id: '1',
  conversationId: '1',
  userId: '1',
  content: 'Hello, world!',
  type: 'text',
  status: 'read',
  attachments: [],
  reactions: [],
  mentions: [],
  isPinned: false,
  isStarred: false,
  createdAt: '2024-01-10T10:00:00Z',
  updatedAt: '2024-01-10T10:00:00Z',
};

describe('MessageItem', () => {
  it('renders message content', () => {
    render(<MessageItem message={mockMessage} />);
    expect(screen.getByText('Hello, world!')).toBeInTheDocument();
  });

  it('shows user ID', () => {
    render(<MessageItem message={mockMessage} />);
    expect(screen.getByText('User 1')).toBeInTheDocument();
  });

  it('shows timestamp', () => {
    render(<MessageItem message={mockMessage} />);
    expect(screen.getByText('10:00 AM')).toBeInTheDocument();
  });

  it('shows edited badge when message is edited', () => {
    const editedMessage = {
      ...mockMessage,
      editedAt: '2024-01-10T10:05:00Z',
    };
    render(<MessageItem message={editedMessage} />);
    expect(screen.getByText('edited')).toBeInTheDocument();
  });

  it('shows pin icon when message is pinned', () => {
    const pinnedMessage = {
      ...mockMessage,
      isPinned: true,
    };
    render(<MessageItem message={pinnedMessage} />);
    expect(screen.getByRole('img', { name: /pin/i })).toBeInTheDocument();
  });

  it('shows star icon when message is starred', () => {
    const starredMessage = {
      ...mockMessage,
      isStarred: true,
    };
    render(<MessageItem message={starredMessage} />);
    expect(screen.getByRole('img', { name: /star/i })).toBeInTheDocument();
  });

  it('shows action menu on hover', () => {
    render(<MessageItem message={mockMessage} />);
    
    const messageContainer = screen.getByText('Hello, world!').closest('.group');
    fireEvent.mouseEnter(messageContainer!);
    
    expect(screen.getByText('Reply')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.getByText('Copy')).toBeInTheDocument();
  });

  it('handles edit action', () => {
    render(<MessageItem message={mockMessage} />);
    
    const messageContainer = screen.getByText('Hello, world!').closest('.group');
    fireEvent.mouseEnter(messageContainer!);
    
    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);
    
    expect(screen.getByDisplayValue('Hello, world!')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('shows reactions when present', () => {
    const messageWithReactions = {
      ...mockMessage,
      reactions: [
        {
          id: '1',
          messageId: '1',
          userId: '2',
          emoji: '👍',
          createdAt: '2024-01-10T10:05:00Z',
        },
      ],
    };
    render(<MessageItem message={messageWithReactions} />);
    expect(screen.getByText('👍')).toBeInTheDocument();
  });

  it('shows attachments when present', () => {
    const messageWithAttachments = {
      ...mockMessage,
      attachments: [
        {
          id: '1',
          messageId: '1',
          type: 'image' as const,
          name: 'screenshot.png',
          url: 'https://example.com/image.png',
          size: 1024,
          mimeType: 'image/png',
          createdAt: '2024-01-10T10:00:00Z',
        },
      ],
    };
    render(<MessageItem message={messageWithAttachments} />);
    expect(screen.getByText('screenshot.png')).toBeInTheDocument();
  });
});
