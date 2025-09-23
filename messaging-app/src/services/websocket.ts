import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private isConnecting = false;

  constructor(
    private userId: string,
    private sessionId: string,
    private onMessage: (message: WebSocketMessage) => void,
    private onError: (error: Event) => void,
    private onClose: (event: CloseEvent) => void
  ) {}

  connect(url: string = 'ws://localhost:8000') {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    const wsUrl = `${url}/ws/${this.userId}/${this.sessionId}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.onMessage(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.isConnecting = false;
        this.onError(error);
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        this.isConnecting = false;
        this.stopHeartbeat();
        this.onClose(event);

        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      this.isConnecting = false;
    }
  }

  private scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });
      }
    }, 30000); // Send ping every 30 seconds
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  send(message: WebSocketMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  sendMessage(conversationId: string, content: string, options: {
    message_type?: 'text' | 'image' | 'file' | 'system';
    reply_to_id?: string;
    thread_id?: string;
    encrypt?: boolean;
  } = {}) {
    this.send({
      type: 'message',
      conversation_id: conversationId,
      content,
      ...options,
    });
  }

  startTyping(conversationId: string) {
    this.send({
      type: 'typing_start',
      conversation_id: conversationId,
    });
  }

  stopTyping(conversationId: string) {
    this.send({
      type: 'typing_stop',
      conversation_id: conversationId,
    });
  }

  acknowledgeMessage(messageId: string) {
    this.send({
      type: 'message_ack',
      message_id: messageId,
    });
  }

  markMessageRead(messageId: string, conversationId: string) {
    this.send({
      type: 'message_read',
      message_id: messageId,
      conversation_id: conversationId,
    });
  }

  addReaction(messageId: string, emoji: string) {
    this.send({
      type: 'reaction',
      message_id: messageId,
      emoji,
      action: 'add',
    });
  }

  removeReaction(messageId: string, emoji: string) {
    this.send({
      type: 'reaction',
      message_id: messageId,
      emoji,
      action: 'remove',
    });
  }

  updatePresence(status: 'online' | 'away' | 'offline' | 'dnd') {
    this.send({
      type: 'presence_update',
      status,
    });
  }

  initiateKeyExchange(recipientId: string) {
    this.send({
      type: 'key_exchange',
      action: 'initiate',
      recipient_id: recipientId,
    });
  }

  completeKeyExchange(exchangeId: string, publicKey: string) {
    this.send({
      type: 'key_exchange',
      action: 'complete',
      exchange_id: exchangeId,
      public_key: publicKey,
    });
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close(1000, 'User disconnected');
      this.ws = null;
    }
  }

  getReadyState() {
    return this.ws?.readyState;
  }

  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Hook for using WebSocket in React components
export function useWebSocket() {
  const { user, setUser } = useAppStore();
  const [wsService, setWsService] = useState<WebSocketService | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!user) return;

    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const service = new WebSocketService(
      user.id,
      sessionId,
      (message) => {
        console.log('WebSocket message received:', message);
        // Handle different message types
        switch (message.type) {
          case 'connection_established':
            setIsConnected(true);
            break;
          case 'new_message':
            // Handle new message
            break;
          case 'typing_indicator':
            // Handle typing indicator
            break;
          case 'presence_update':
            // Handle presence update
            break;
          case 'pong':
            // Handle heartbeat response
            break;
          default:
            console.log('Unknown message type:', message.type);
        }
      },
      (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      },
      (event) => {
        console.log('WebSocket closed:', event);
        setIsConnected(false);
      }
    );

    setWsService(service);
    service.connect();

    return () => {
      service.disconnect();
    };
  }, [user]);

  return {
    wsService,
    isConnected,
  };
}
