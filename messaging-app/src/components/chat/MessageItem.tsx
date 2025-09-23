'use client';

import { useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  MoreVertical, 
  Reply, 
  Edit, 
  Trash2, 
  Star, 
  Pin, 
  Copy,
  Check,
  CheckCheck,
  Clock,
  X
} from 'lucide-react';
import { formatTime, formatDate } from '@/lib/utils';
import { Message } from '@/types';

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const [showActions, setShowActions] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const getStatusIcon = (status: Message['status']) => {
    switch (status) {
      case 'sending':
        return <Clock className="h-3 w-3 text-muted-foreground" />;
      case 'sent':
        return <Check className="h-3 w-3 text-muted-foreground" />;
      case 'delivered':
        return <CheckCheck className="h-3 w-3 text-muted-foreground" />;
      case 'read':
        return <CheckCheck className="h-3 w-3 text-blue-500" />;
      case 'failed':
        return <X className="h-3 w-3 text-destructive" />;
      default:
        return null;
    }
  };

  const formatMessageDate = (date: string) => {
    const messageDate = new Date(date);
    const now = new Date();
    const isToday = messageDate.toDateString() === now.toDateString();
    
    if (isToday) {
      return formatTime(date);
    } else {
      return formatDate(date);
    }
  };

  const handleReaction = (emoji: string) => {
    // TODO: Implement reaction handling
    console.log('React with:', emoji);
  };

  const handleReply = () => {
    // TODO: Implement reply handling
    console.log('Reply to message:', message.id);
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleDelete = () => {
    // TODO: Implement delete handling
    console.log('Delete message:', message.id);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
  };

  return (
    <div 
      className="group relative"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex gap-3">
        <Avatar className="w-8 h-8 flex-shrink-0">
          <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${message.userId}`} />
          <AvatarFallback>
            {message.userId.charAt(0).toUpperCase()}
          </AvatarFallback>
        </Avatar>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium">User {message.userId}</span>
            <span className="text-xs text-muted-foreground">
              {formatMessageDate(message.createdAt)}
            </span>
            {message.editedAt && (
              <Badge variant="outline" className="text-xs">
                edited
              </Badge>
            )}
            {message.isPinned && (
              <Pin className="h-3 w-3 text-yellow-500" />
            )}
            {message.isStarred && (
              <Star className="h-3 w-3 text-yellow-500" />
            )}
          </div>

          <div className="space-y-2">
            {isEditing ? (
              <div className="space-y-2">
                <textarea
                  defaultValue={message.content}
                  className="w-full p-2 border border-input rounded-md resize-none"
                  rows={3}
                  autoFocus
                />
                <div className="flex gap-2">
                  <Button size="sm">Save</Button>
                  <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="prose prose-sm max-w-none">
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            )}

            {/* Attachments */}
            {message.attachments.length > 0 && (
              <div className="space-y-2">
                {message.attachments.map((attachment) => (
                  <div key={attachment.id} className="border border-border rounded-lg p-3">
                    {attachment.type === 'image' ? (
                      <img
                        src={attachment.url}
                        alt={attachment.name}
                        className="max-w-xs rounded-md"
                      />
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-muted rounded flex items-center justify-center">
                          📄
                        </div>
                        <div>
                          <p className="text-sm font-medium">{attachment.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {(attachment.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Reactions */}
            {message.reactions.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {message.reactions.map((reaction) => (
                  <Button
                    key={reaction.id}
                    variant="outline"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => handleReaction(reaction.emoji)}
                  >
                    {reaction.emoji} {reaction.userId}
                  </Button>
                ))}
              </div>
            )}

            {/* Message Status */}
            <div className="flex items-center gap-1">
              {getStatusIcon(message.status)}
              {message.status === 'failed' && (
                <Button variant="ghost" size="sm" className="h-6 px-2 text-xs">
                  Retry
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Action Menu */}
      {showActions && (
        <div className="absolute top-0 right-0 bg-background border border-border rounded-lg shadow-lg p-1 z-10">
          <div className="flex flex-col">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 justify-start"
              onClick={handleReply}
            >
              <Reply className="h-3 w-3 mr-2" />
              Reply
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 justify-start"
              onClick={handleEdit}
            >
              <Edit className="h-3 w-3 mr-2" />
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 justify-start"
              onClick={handleCopy}
            >
              <Copy className="h-3 w-3 mr-2" />
              Copy
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 justify-start"
              onClick={() => handleReaction('👍')}
            >
              👍 React
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 justify-start text-destructive"
              onClick={handleDelete}
            >
              <Trash2 className="h-3 w-3 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
