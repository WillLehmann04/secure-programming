'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Search, 
  MessageSquare, 
  Users, 
  Hash,
  Star,
  Archive,
  MoreVertical,
  Plus
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { formatDate } from '@/lib/utils';
import { Conversation } from '@/types';
import { apiClient } from '@/services/api';

export function ConversationList() {
  const { currentConversationId, setCurrentConversationId, setCommandPaletteOpen } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'unread' | 'pinned'>('all');

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations', { search: searchQuery, filter }],
    queryFn: async () => {
      const params: any = {};
      if (searchQuery) params.search = searchQuery;
      if (filter === 'unread') params.has_unread = true;
      
      const response = await apiClient.getConversations(params);
      return response.conversations;
    },
  });

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      setCommandPaletteOpen(true);
    }
  };

  const getConversationIcon = (conversation: Conversation) => {
    switch (conversation.type) {
      case 'channel':
        return <Hash className="h-4 w-4 text-primary" />;
      case 'group':
        return <Users className="h-4 w-4 text-orange-500" />;
      case 'dm':
        return <MessageSquare className="h-4 w-4 text-blue-500" />;
      default:
        return <MessageSquare className="h-4 w-4" />;
    }
  };

  const getStatusColor = (conversation: Conversation) => {
    if (conversation.unreadCount > 0) {
      return 'bg-green-500';
    }
    return 'bg-muted-foreground';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">Messages</h1>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCommandPaletteOpen(true)}
              title="Command Palette (⌘K)"
            >
              <Search className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-10"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Button
            variant={filter === 'all' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setFilter('all')}
          >
            All
          </Button>
          <Button
            variant={filter === 'unread' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setFilter('unread')}
          >
            Unread
          </Button>
          <Button
            variant={filter === 'pinned' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setFilter('pinned')}
          >
            <Star className="h-4 w-4 mr-1" />
            Pinned
          </Button>
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto">
        {conversations?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No conversations found</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery ? 'Try adjusting your search terms' : 'Start a new conversation'}
            </p>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Message
            </Button>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {conversations?.map((conversation) => (
              <div
                key={conversation.id}
                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                  currentConversationId === conversation.id
                    ? 'bg-accent'
                    : 'hover:bg-accent/50'
                }`}
                onClick={() => setCurrentConversationId(conversation.id)}
              >
                <div className="relative">
                  {conversation.type === 'dm' ? (
                    <Avatar className="w-10 h-10">
                      <AvatarImage src={conversation.avatar} />
                      <AvatarFallback>
                        {conversation.name.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                      {getConversationIcon(conversation)}
                    </div>
                  )}
                  {conversation.unreadCount > 0 && (
                    <div className={`absolute -top-1 -right-1 w-3 h-3 ${getStatusColor(conversation)} rounded-full border-2 border-background`}></div>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium truncate">{conversation.name}</p>
                    {conversation.lastMessage && (
                      <span className="text-xs text-muted-foreground">
                        {formatDate(conversation.lastMessage.createdAt)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-muted-foreground truncate">
                      {conversation.lastMessage?.content || 'No messages yet'}
                    </p>
                    {conversation.isPinned && (
                      <Star className="h-3 w-3 text-yellow-500" />
                    )}
                    {conversation.isMuted && (
                      <Archive className="h-3 w-3 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {conversation.unreadCount > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {conversation.unreadCount}
                  </Badge>
                )}

                <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
