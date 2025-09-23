'use client';

import { useQuery } from '@tanstack/react-query';
import { Virtuoso } from 'react-virtuoso';
import { MessageItem } from './MessageItem';
import { Message } from '@/types';
import { apiClient } from '@/services/api';

interface MessageListProps {
  conversationId: string;
}

export function MessageList({ conversationId }: MessageListProps) {
  const { data: messages, isLoading, error } = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: async () => {
      const response = await apiClient.getMessages(conversationId);
      return response.messages.reverse(); // Reverse to show oldest first
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">Failed to load messages</h3>
          <p className="text-muted-foreground">Please try again later</p>
        </div>
      </div>
    );
  }

  if (!messages || messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">No messages yet</h3>
          <p className="text-muted-foreground">Start the conversation!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full">
      <Virtuoso
        data={messages}
        itemContent={(index, message) => (
          <div className="px-4 py-2">
            <MessageItem message={message} />
          </div>
        )}
        followOutput="smooth"
        className="message-list scrollbar-thin"
      />
    </div>
  );
}
