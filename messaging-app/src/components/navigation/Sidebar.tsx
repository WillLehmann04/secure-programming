'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  MessageSquare, 
  Users, 
  Settings, 
  Menu,
  Plus,
  Star,
  Archive,
  Hash
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { formatDate } from '@/lib/utils';

export function Sidebar() {
  const { user, setSidebarOpen, setCommandPaletteOpen } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      setCommandPaletteOpen(true);
    }
  };

  return (
    <div className="flex flex-col h-full bg-card">
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
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden"
            >
              <Menu className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-10"
          />
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-6">
          {/* Quick Actions */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                Quick Actions
              </h2>
              <Button variant="ghost" size="icon" className="h-6 w-6">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-1">
              <Button variant="ghost" className="w-full justify-start">
                <MessageSquare className="h-4 w-4 mr-2" />
                New Message
              </Button>
              <Button variant="ghost" className="w-full justify-start">
                <Users className="h-4 w-4 mr-2" />
                New Group
              </Button>
            </div>
          </div>

          {/* Pinned Conversations */}
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Pinned
            </h2>
            <div className="space-y-1">
              <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Hash className="h-4 w-4 text-primary" />
                  </div>
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-background"></div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">General</p>
                    <Badge variant="secondary" className="text-xs">
                      3
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    Hey everyone! Check out this new design...
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate('2024-01-10T10:30:00Z')}
                </div>
              </div>

              <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full bg-orange-500/10 flex items-center justify-center">
                    <Users className="h-4 w-4 text-orange-500" />
                  </div>
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-background"></div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">Design Team</p>
                    <Badge variant="secondary" className="text-xs">
                      1
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    Design review meeting at 2 PM today...
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate('2024-01-10T09:15:00Z')}
                </div>
              </div>
            </div>
          </div>

          {/* All Conversations */}
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              All Conversations
            </h2>
            <div className="space-y-1">
              <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                    <Users className="h-4 w-4 text-blue-500" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">Development</p>
                  <p className="text-xs text-muted-foreground truncate">
                    Latest updates on the project...
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate('2024-01-09T16:45:00Z')}
                </div>
              </div>

              <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer">
                <div className="relative">
                  <Avatar className="w-8 h-8">
                    <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=alice" />
                    <AvatarFallback>AJ</AvatarFallback>
                  </Avatar>
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-background"></div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">Alice Johnson</p>
                    <Badge variant="secondary" className="text-xs">
                      2
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    Thanks for the feedback on the user flow...
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate('2024-01-10T11:20:00Z')}
                </div>
              </div>

              <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer">
                <div className="relative">
                  <Avatar className="w-8 h-8">
                    <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=bob" />
                    <AvatarFallback>BS</AvatarFallback>
                  </Avatar>
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-yellow-500 rounded-full border-2 border-background"></div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">Bob Smith</p>
                  <p className="text-xs text-muted-foreground truncate">
                    Looking great! The color scheme is perfect...
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate('2024-01-09T14:30:00Z')}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* User Profile */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3">
          <Avatar className="w-8 h-8">
            <AvatarImage src={user?.avatar} />
            <AvatarFallback>
              {user?.displayName?.split(' ').map(n => n[0]).join('')}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.displayName}</p>
            <p className="text-xs text-muted-foreground truncate">
              {user?.status === 'online' ? 'Online' : 
               user?.status === 'away' ? 'Away' :
               user?.status === 'dnd' ? 'Do not disturb' : 'Offline'}
            </p>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
