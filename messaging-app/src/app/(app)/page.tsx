'use client';

import { ConversationList } from '@/components/navigation/ConversationList';
import { MessageList } from '@/components/chat/MessageList';
import { Composer } from '@/components/chat/Composer';
import { useAppStore } from '@/store/useAppStore';

export default function AppPage() {
  const { currentConversationId } = useAppStore();

  return (
    <div className="flex h-full">
      {/* Conversation List */}
      <div className="w-80 border-r border-border bg-card">
        <ConversationList />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {currentConversationId ? (
          <>
            <div className="flex-1 overflow-hidden">
              <MessageList conversationId={currentConversationId} />
            </div>
            <div className="border-t border-border p-4">
              <Composer conversationId={currentConversationId} />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-muted-foreground mb-2">
                Welcome to your messages
              </h2>
              <p className="text-muted-foreground">
                Select a conversation to start chatting
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
