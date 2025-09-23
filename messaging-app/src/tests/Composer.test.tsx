import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Composer } from '@/components/chat/Composer';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('Composer', () => {
  it('renders composer input', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
  });

  it('shows send button', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('shows attachment button', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    expect(screen.getByRole('button', { name: /attach/i })).toBeInTheDocument();
  });

  it('shows emoji button', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    expect(screen.getByRole('button', { name: /emoji/i })).toBeInTheDocument();
  });

  it('expands on focus', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.focus(textarea);
    
    expect(screen.getByText('Press Enter to send, Shift+Enter for new line')).toBeInTheDocument();
  });

  it('shows toolbar on focus', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.focus(textarea);
    
    expect(screen.getByRole('button', { name: /bold/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /italic/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /code/i })).toBeInTheDocument();
  });

  it('shows slash commands hint', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.focus(textarea);
    fireEvent.change(textarea, { target: { value: '/' } });
    
    expect(screen.getByText('Slash commands:')).toBeInTheDocument();
    expect(screen.getByText('/giphy - Search for a GIF')).toBeInTheDocument();
    expect(screen.getByText('/shrug - ¯\_(ツ)_/¯')).toBeInTheDocument();
  });

  it('handles text input', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Hello, world!' } });
    
    expect(textarea).toHaveValue('Hello, world!');
  });

  it('enables send button when text is entered', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const textarea = screen.getByPlaceholderText('Type a message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    expect(sendButton).toBeDisabled();
    
    fireEvent.change(textarea, { target: { value: 'Hello!' } });
    
    expect(sendButton).not.toBeDisabled();
  });

  it('handles file upload', () => {
    render(
      <TestWrapper>
        <Composer conversationId="1" />
      </TestWrapper>
    );
    
    const fileInput = screen.getByRole('button', { name: /attach/i });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    
    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    
    // File input should be triggered
    expect(input).toBeInTheDocument();
  });
});
