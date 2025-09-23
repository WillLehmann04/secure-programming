const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public response?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ApiClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    this.loadToken();
  }

  private loadToken() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('access_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    const config: RequestInit = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          errorData.detail || `HTTP ${response.status}`,
          response.status,
          errorData
        );
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        error instanceof Error ? error.message : 'Network error',
        0
      );
    }
  }

  // Auth endpoints
  async signIn(email: string, password: string) {
    const response = await this.request<{
      success: boolean;
      user: any;
      access_token: string;
      refresh_token: string;
    }>('/api/auth/signin', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (response.success) {
      this.setToken(response.access_token);
    }

    return response;
  }

  async signUp(email: string, username: string, displayName: string, password: string) {
    const response = await this.request<{
      success: boolean;
      user: any;
      access_token: string;
      refresh_token: string;
    }>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, username, display_name: displayName, password }),
    });

    if (response.success) {
      this.setToken(response.access_token);
    }

    return response;
  }

  async signOut() {
    try {
      await this.request('/api/auth/signout', { method: 'POST' });
    } finally {
      this.clearToken();
    }
  }

  async getCurrentUser() {
    return this.request<{
      success: boolean;
      user: any;
    }>('/api/auth/me');
  }

  // Conversations endpoints
  async getConversations(params?: {
    search?: string;
    conversation_type?: string;
    has_unread?: boolean;
    limit?: number;
    offset?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }

    return this.request<{
      success: boolean;
      conversations: any[];
      total: number;
    }>(`/api/conversations?${searchParams}`);
  }

  async createConversation(data: {
    name?: string;
    description?: string;
    conversation_type: 'dm' | 'group' | 'channel';
    participant_ids: string[];
  }) {
    return this.request<{
      success: boolean;
      conversation: any;
    }>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getConversation(conversationId: string) {
    return this.request<{
      success: boolean;
      conversation: any;
    }>(`/api/conversations/${conversationId}`);
  }

  // Messages endpoints
  async getMessages(conversationId: string, params?: {
    limit?: number;
    offset?: number;
    before?: string;
  }) {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }

    return this.request<{
      success: boolean;
      messages: any[];
      has_more: boolean;
    }>(`/api/conversations/${conversationId}/messages?${searchParams}`);
  }

  async sendMessage(conversationId: string, data: {
    content: string;
    message_type?: 'text' | 'image' | 'file' | 'system';
    reply_to_id?: string;
    thread_id?: string;
    encrypt?: boolean;
  }) {
    return this.request<{
      success: boolean;
      message: any;
    }>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async editMessage(messageId: string, content: string) {
    return this.request<{
      success: boolean;
      message: any;
    }>(`/api/messages/${messageId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
  }

  async deleteMessage(messageId: string) {
    return this.request<{
      success: boolean;
      message: string;
    }>(`/api/messages/${messageId}`, {
      method: 'DELETE',
    });
  }

  async addReaction(messageId: string, emoji: string) {
    return this.request<{
      success: boolean;
      reaction: any;
    }>(`/api/messages/${messageId}/reactions`, {
      method: 'POST',
      body: JSON.stringify({ emoji }),
    });
  }

  async removeReaction(messageId: string, emoji: string) {
    return this.request<{
      success: boolean;
      message: string;
    }>(`/api/messages/${messageId}/reactions/${emoji}`, {
      method: 'DELETE',
    });
  }

  // Users endpoints
  async getUsers(params?: {
    search?: string;
    limit?: number;
    offset?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }

    return this.request<{
      success: boolean;
      users: any[];
      total: number;
    }>(`/api/users?${searchParams}`);
  }

  async getUser(userId: string) {
    return this.request<{
      success: boolean;
      user: any;
    }>(`/api/users/${userId}`);
  }

  // File upload
  async uploadFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseURL}/api/files/upload`, {
      method: 'POST',
      headers: {
        Authorization: this.token ? `Bearer ${this.token}` : '',
      },
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        errorData.detail || `HTTP ${response.status}`,
        response.status,
        errorData
      );
    }

    return response.json();
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
export { ApiError };
