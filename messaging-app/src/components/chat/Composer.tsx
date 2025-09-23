'use client';

import { useState, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { 
  Send, 
  Paperclip, 
  Smile, 
  Bold, 
  Italic, 
  Code,
  Link,
  Plus
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { apiClient } from '@/services/api';

const messageSchema = z.object({
  content: z.string().min(1, 'Message cannot be empty'),
});

type MessageForm = z.infer<typeof messageSchema>;

interface ComposerProps {
  conversationId: string;
}

export function Composer({ conversationId }: ComposerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showToolbar, setShowToolbar] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { settings, setUploadProgress } = useAppStore();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
  } = useForm<MessageForm>({
    resolver: zodResolver(messageSchema),
  });

  const content = watch('content', '');

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [content]);

  const onSubmit = async (data: MessageForm) => {
    try {
      const response = await apiClient.sendMessage(conversationId, {
        content: data.content,
        message_type: 'text',
      });

      if (response.success) {
        reset();
        setIsExpanded(false);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (settings.sendBehavior === 'enter') {
        if (!e.shiftKey) {
          e.preventDefault();
          handleSubmit(onSubmit)();
        }
      } else {
        if (e.shiftKey) {
          e.preventDefault();
          handleSubmit(onSubmit)();
        }
      }
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fileId = Math.random().toString(36).substr(2, 9);
    setUploadProgress(fileId, 0);

    // Simulate upload progress
    const interval = setInterval(() => {
      setUploadProgress(fileId, (prev) => {
        const newProgress = prev + Math.random() * 30;
        if (newProgress >= 100) {
          clearInterval(interval);
          setTimeout(() => setUploadProgress(fileId, 100), 100);
          return 100;
        }
        return newProgress;
      });
    }, 200);
  };

  const insertText = (before: string, after: string = '') => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = content.substring(start, end);
    const newText = before + selectedText + after;
    
    setValue('content', content.substring(0, start) + newText + content.substring(end));
    
    // Focus and set cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + before.length, start + before.length + selectedText.length);
    }, 0);
  };

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      {showToolbar && (
        <div className="flex items-center gap-1 p-2 bg-muted rounded-lg">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => insertText('**', '**')}
            title="Bold"
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => insertText('*', '*')}
            title="Italic"
          >
            <Italic className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => insertText('`', '`')}
            title="Code"
          >
            <Code className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => insertText('[', '](url)')}
            title="Link"
          >
            <Link className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Composer */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-2">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              {...register('content')}
              ref={textareaRef}
              placeholder="Type a message..."
              className="w-full min-h-[40px] max-h-32 px-3 py-2 border border-input rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              onKeyDown={handleKeyDown}
              onFocus={() => {
                setIsExpanded(true);
                setShowToolbar(true);
              }}
              onBlur={() => {
                if (!content.trim()) {
                  setIsExpanded(false);
                  setShowToolbar(false);
                }
              }}
              rows={1}
            />
            
            {/* Slash commands hint */}
            {content.startsWith('/') && (
              <div className="absolute bottom-full left-0 mb-2 bg-popover border border-border rounded-lg shadow-lg p-2 z-10">
                <div className="text-sm text-muted-foreground mb-1">Slash commands:</div>
                <div className="space-y-1">
                  <div className="px-2 py-1 hover:bg-accent rounded cursor-pointer">
                    /giphy - Search for a GIF
                  </div>
                  <div className="px-2 py-1 hover:bg-accent rounded cursor-pointer">
                    /shrug - ¯\_(ツ)_/¯
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1">
            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={handleFileUpload}
              accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => document.getElementById('file-upload')?.click()}
              title="Attach file"
            >
              <Paperclip className="h-4 w-4" />
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="icon"
              title="Add emoji"
            >
              <Smile className="h-4 w-4" />
            </Button>

            <Button
              type="submit"
              size="icon"
              disabled={!content.trim()}
              title="Send message"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Send behavior hint */}
        <div className="text-xs text-muted-foreground">
          {settings.sendBehavior === 'enter' 
            ? 'Press Enter to send, Shift+Enter for new line'
            : 'Press Shift+Enter to send, Enter for new line'
          }
        </div>
      </form>
    </div>
  );
}
