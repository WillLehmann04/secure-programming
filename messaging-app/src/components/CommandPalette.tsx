'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  MessageSquare, 
  Users, 
  Hash,
  User,
  Settings,
  X
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { formatDate } from '@/lib/utils';

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen, setCurrentConversationId } = useAppStore();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: searchResults, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: async () => {
      if (!query.trim()) return [];
      
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const result = await response.json();
      return result.data || [];
    },
    enabled: query.length > 0,
  });

  const commands = [
    {
      id: 'new-message',
      type: 'action',
      title: 'New Message',
      subtitle: 'Start a new conversation',
      icon: MessageSquare,
      action: () => {
        console.log('New message');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'new-group',
      type: 'action',
      title: 'New Group',
      subtitle: 'Create a group conversation',
      icon: Users,
      action: () => {
        console.log('New group');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'settings',
      type: 'action',
      title: 'Settings',
      subtitle: 'Open app settings',
      icon: Settings,
      action: () => {
        console.log('Settings');
        setCommandPaletteOpen(false);
      },
    },
  ];

  const allResults = [
    ...(searchResults || []),
    ...commands,
  ];

  useEffect(() => {
    if (commandPaletteOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [commandPaletteOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      
      if (commandPaletteOpen) {
        if (e.key === 'Escape') {
          setCommandPaletteOpen(false);
        } else if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSelectedIndex((prev) => 
            prev < allResults.length - 1 ? prev + 1 : 0
          );
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSelectedIndex((prev) => 
            prev > 0 ? prev - 1 : allResults.length - 1
          );
        } else if (e.key === 'Enter') {
          e.preventDefault();
          const selectedItem = allResults[selectedIndex];
          if (selectedItem) {
            if (selectedItem.action) {
              selectedItem.action();
            } else if (selectedItem.type === 'conversation') {
              setCurrentConversationId(selectedItem.id);
              setCommandPaletteOpen(false);
            }
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, selectedIndex, allResults, setCommandPaletteOpen, setCurrentConversationId]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (listRef.current && selectedIndex >= 0) {
      const selectedElement = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({
          block: 'nearest',
          behavior: 'smooth',
        });
      }
    }
  }, [selectedIndex]);

  if (!commandPaletteOpen) return null;

  const getItemIcon = (item: any) => {
    if (item.icon) {
      const Icon = item.icon;
      return <Icon className="h-4 w-4" />;
    }
    
    switch (item.type) {
      case 'conversation':
        return <MessageSquare className="h-4 w-4" />;
      case 'user':
        return <User className="h-4 w-4" />;
      case 'message':
        return <Hash className="h-4 w-4" />;
      default:
        return <Search className="h-4 w-4" />;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center pt-20 z-50">
      <div className="bg-background border border-border rounded-lg shadow-lg w-full max-w-2xl mx-4">
        {/* Header */}
        <div className="flex items-center gap-2 p-4 border-b border-border">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            ref={inputRef}
            placeholder="Search conversations, users, or commands..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border-0 shadow-none focus-visible:ring-0 text-lg"
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCommandPaletteOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
            </div>
          ) : allResults.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              {query ? 'No results found' : 'Start typing to search...'}
            </div>
          ) : (
            <div ref={listRef} className="py-2">
              {allResults.map((item, index) => (
                <div
                  key={item.id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer ${
                    index === selectedIndex ? 'bg-accent' : 'hover:bg-accent/50'
                  }`}
                  onClick={() => {
                    if (item.action) {
                      item.action();
                    } else if (item.type === 'conversation') {
                      setCurrentConversationId(item.id);
                      setCommandPaletteOpen(false);
                    }
                  }}
                >
                  <div className="flex-shrink-0">
                    {getItemIcon(item)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{item.title}</p>
                      {item.type && (
                        <Badge variant="outline" className="text-xs">
                          {item.type}
                        </Badge>
                      )}
                    </div>
                    {item.subtitle && (
                      <p className="text-sm text-muted-foreground truncate">
                        {item.subtitle}
                      </p>
                    )}
                    {item.content && (
                      <p className="text-sm text-muted-foreground truncate">
                        {item.content}
                      </p>
                    )}
                    {item.timestamp && (
                      <p className="text-xs text-muted-foreground">
                        {formatDate(item.timestamp)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span>↑↓ Navigate</span>
              <span>↵ Select</span>
              <span>⎋ Close</span>
            </div>
            <span>⌘K to open</span>
          </div>
        </div>
      </div>
    </div>
  );
}
