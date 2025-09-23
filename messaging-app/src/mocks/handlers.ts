import { http, HttpResponse } from 'msw';
import { users, conversations, messages, attachments, reactions } from './seed';
import { ApiResponse, PaginatedResponse } from '@/types';

const API_BASE = '/api';

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE}/auth/signin`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string };
    
    if (body.email === 'alice@example.com' && body.password === 'password') {
      return HttpResponse.json<ApiResponse<{ user: typeof users[0]; token: string }>>({
        data: {
          user: users[0],
          token: 'mock-jwt-token',
        },
        success: true,
      });
    }
    
    return HttpResponse.json<ApiResponse<null>>({
      data: null,
      success: false,
      message: 'Invalid credentials',
    }, { status: 401 });
  }),

  http.post(`${API_BASE}/auth/signup`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string; displayName: string };
    
    return HttpResponse.json<ApiResponse<{ user: typeof users[0]; token: string }>>({
      data: {
        user: {
          ...users[0],
          email: body.email,
          displayName: body.displayName,
        },
        token: 'mock-jwt-token',
      },
      success: true,
    });
  }),

  http.post(`${API_BASE}/auth/magic-link`, async ({ request }) => {
    const body = await request.json() as { email: string };
    
    return HttpResponse.json<ApiResponse<{ message: string }>>({
      data: { message: 'Magic link sent to your email' },
      success: true,
    });
  }),

  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json<ApiResponse<typeof users[0]>>({
      data: users[0],
      success: true,
    });
  }),

  // Users endpoints
  http.get(`${API_BASE}/users`, ({ request }) => {
    const url = new URL(request.url);
    const search = url.searchParams.get('search') || '';
    const limit = parseInt(url.searchParams.get('limit') || '20');
    
    const filteredUsers = users.filter(user =>
      user.displayName.toLowerCase().includes(search.toLowerCase()) ||
      user.handle.toLowerCase().includes(search.toLowerCase())
    ).slice(0, limit);

    return HttpResponse.json<PaginatedResponse<typeof users[0]>>({
      data: filteredUsers,
      pagination: {
        page: 1,
        limit,
        total: filteredUsers.length,
        hasMore: false,
      },
    });
  }),

  http.get(`${API_BASE}/users/:id`, ({ params }) => {
    const user = users.find(u => u.id === params.id);
    
    if (!user) {
      return HttpResponse.json<ApiResponse<null>>({
        data: null,
        success: false,
        message: 'User not found',
      }, { status: 404 });
    }

    return HttpResponse.json<ApiResponse<typeof user>>({
      data: user,
      success: true,
    });
  }),

  // Conversations endpoints
  http.get(`${API_BASE}/conversations`, ({ request }) => {
    const url = new URL(request.url);
    const search = url.searchParams.get('search') || '';
    const type = url.searchParams.get('type') as 'dm' | 'group' | 'channel' | null;
    const hasUnread = url.searchParams.get('hasUnread') === 'true';
    
    let filteredConversations = conversations;

    if (search) {
      filteredConversations = filteredConversations.filter(conv =>
        conv.name.toLowerCase().includes(search.toLowerCase()) ||
        conv.description?.toLowerCase().includes(search.toLowerCase())
      );
    }

    if (type) {
      filteredConversations = filteredConversations.filter(conv => conv.type === type);
    }

    if (hasUnread) {
      filteredConversations = filteredConversations.filter(conv => conv.unreadCount > 0);
    }

    return HttpResponse.json<PaginatedResponse<typeof conversations[0]>>({
      data: filteredConversations,
      pagination: {
        page: 1,
        limit: 50,
        total: filteredConversations.length,
        hasMore: false,
      },
    });
  }),

  http.get(`${API_BASE}/conversations/:id`, ({ params }) => {
    const conversation = conversations.find(c => c.id === params.id);
    
    if (!conversation) {
      return HttpResponse.json<ApiResponse<null>>({
        data: null,
        success: false,
        message: 'Conversation not found',
      }, { status: 404 });
    }

    return HttpResponse.json<ApiResponse<typeof conversation>>({
      data: conversation,
      success: true,
    });
  }),

  http.post(`${API_BASE}/conversations`, async ({ request }) => {
    const body = await request.json() as { name: string; type: 'dm' | 'group' | 'channel'; participants: string[] };
    
    const newConversation = {
      id: (conversations.length + 1).toString(),
      name: body.name,
      type: body.type,
      participants: body.participants,
      unreadCount: 0,
      isPinned: false,
      isMuted: false,
      isArchived: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    conversations.push(newConversation);

    return HttpResponse.json<ApiResponse<typeof newConversation>>({
      data: newConversation,
      success: true,
    });
  }),

  // Messages endpoints
  http.get(`${API_BASE}/conversations/:id/messages`, ({ params, request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const before = url.searchParams.get('before');
    
    let conversationMessages = messages.filter(m => m.conversationId === params.id);
    
    if (before) {
      const beforeDate = new Date(before);
      conversationMessages = conversationMessages.filter(m => new Date(m.createdAt) < beforeDate);
    }

    const startIndex = (page - 1) * limit;
    const endIndex = startIndex + limit;
    const paginatedMessages = conversationMessages
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(startIndex, endIndex);

    return HttpResponse.json<PaginatedResponse<typeof messages[0]>>({
      data: paginatedMessages,
      pagination: {
        page,
        limit,
        total: conversationMessages.length,
        hasMore: endIndex < conversationMessages.length,
      },
    });
  }),

  http.post(`${API_BASE}/conversations/:id/messages`, async ({ params, request }) => {
    const body = await request.json() as { content: string; replyToId?: string; threadId?: string };
    
    const newMessage = {
      id: (messages.length + 1).toString(),
      conversationId: params.id as string,
      userId: users[0].id,
      content: body.content,
      type: 'text' as const,
      status: 'sending' as const,
      attachments: [],
      reactions: [],
      mentions: [],
      isPinned: false,
      isStarred: false,
      replyToId: body.replyToId,
      threadId: body.threadId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    messages.push(newMessage);

    // Simulate async processing
    setTimeout(() => {
      const messageIndex = messages.findIndex(m => m.id === newMessage.id);
      if (messageIndex !== -1) {
        messages[messageIndex].status = 'sent';
      }
    }, 1000);

    return HttpResponse.json<ApiResponse<typeof newMessage>>({
      data: newMessage,
      success: true,
    });
  }),

  http.put(`${API_BASE}/messages/:id`, async ({ params, request }) => {
    const body = await request.json() as { content: string };
    const messageIndex = messages.findIndex(m => m.id === params.id);
    
    if (messageIndex === -1) {
      return HttpResponse.json<ApiResponse<null>>({
        data: null,
        success: false,
        message: 'Message not found',
      }, { status: 404 });
    }

    messages[messageIndex].content = body.content;
    messages[messageIndex].editedAt = new Date().toISOString();
    messages[messageIndex].updatedAt = new Date().toISOString();

    return HttpResponse.json<ApiResponse<typeof messages[messageIndex]>>({
      data: messages[messageIndex],
      success: true,
    });
  }),

  http.delete(`${API_BASE}/messages/:id`, ({ params }) => {
    const messageIndex = messages.findIndex(m => m.id === params.id);
    
    if (messageIndex === -1) {
      return HttpResponse.json<ApiResponse<null>>({
        data: null,
        success: false,
        message: 'Message not found',
      }, { status: 404 });
    }

    messages.splice(messageIndex, 1);

    return HttpResponse.json<ApiResponse<null>>({
      data: null,
      success: true,
    });
  }),

  // Reactions endpoints
  http.post(`${API_BASE}/messages/:id/reactions`, async ({ params, request }) => {
    const body = await request.json() as { emoji: string };
    
    const newReaction = {
      id: (reactions.length + 1).toString(),
      messageId: params.id as string,
      userId: users[0].id,
      emoji: body.emoji,
      createdAt: new Date().toISOString(),
    };

    reactions.push(newReaction);

    return HttpResponse.json<ApiResponse<typeof newReaction>>({
      data: newReaction,
      success: true,
    });
  }),

  http.delete(`${API_BASE}/messages/:id/reactions/:emoji`, ({ params }) => {
    const reactionIndex = reactions.findIndex(
      r => r.messageId === params.id && r.emoji === params.emoji && r.userId === users[0].id
    );
    
    if (reactionIndex !== -1) {
      reactions.splice(reactionIndex, 1);
    }

    return HttpResponse.json<ApiResponse<null>>({
      data: null,
      success: true,
    });
  }),

  // Search endpoints
  http.get(`${API_BASE}/search`, ({ request }) => {
    const url = new URL(request.url);
    const query = url.searchParams.get('q') || '';
    const type = url.searchParams.get('type') as 'message' | 'conversation' | 'user' | null;
    
    const results = [];
    
    if (!type || type === 'message') {
      const messageResults = messages
        .filter(m => m.content.toLowerCase().includes(query.toLowerCase()))
        .map(m => ({
          type: 'message' as const,
          id: m.id,
          title: m.content.substring(0, 50) + (m.content.length > 50 ? '...' : ''),
          content: m.content,
          conversationId: m.conversationId,
          conversationName: conversations.find(c => c.id === m.conversationId)?.name,
          timestamp: m.createdAt,
          highlights: [query],
        }));
      results.push(...messageResults);
    }

    if (!type || type === 'conversation') {
      const conversationResults = conversations
        .filter(c => c.name.toLowerCase().includes(query.toLowerCase()))
        .map(c => ({
          type: 'conversation' as const,
          id: c.id,
          title: c.name,
          content: c.description,
          timestamp: c.updatedAt,
          highlights: [query],
        }));
      results.push(...conversationResults);
    }

    if (!type || type === 'user') {
      const userResults = users
        .filter(u => 
          u.displayName.toLowerCase().includes(query.toLowerCase()) ||
          u.handle.toLowerCase().includes(query.toLowerCase())
        )
        .map(u => ({
          type: 'user' as const,
          id: u.id,
          title: u.displayName,
          content: u.bio,
          timestamp: u.lastSeen,
          highlights: [query],
        }));
      results.push(...userResults);
    }

    return HttpResponse.json<ApiResponse<typeof results>>({
      data: results,
      success: true,
    });
  }),

  // Upload endpoints
  http.post(`${API_BASE}/upload`, async ({ request }) => {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      return HttpResponse.json<ApiResponse<null>>({
        data: null,
        success: false,
        message: 'No file provided',
      }, { status: 400 });
    }

    // Simulate upload progress
    const uploadId = Math.random().toString(36).substr(2, 9);
    
    return HttpResponse.json<ApiResponse<{ uploadId: string; url: string }>>({
      data: {
        uploadId,
        url: `https://example.com/uploads/${uploadId}`,
      },
      success: true,
    });
  }),
];
