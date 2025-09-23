# Secure Messaging App

A comprehensive, secure messaging application built with Next.js frontend and Python FastAPI backend, featuring real-time WebSocket communication, end-to-end encryption, and modern UI/UX.

## 🚀 Features

### Frontend (Next.js + TypeScript)
- **Modern UI**: Built with Tailwind CSS and shadcn/ui components
- **Real-time Communication**: WebSocket integration for instant messaging
- **Responsive Design**: 3-pane desktop layout, mobile-friendly tabs
- **Accessibility**: WCAG 2.1 AA compliant with full keyboard navigation
- **Internationalization**: Multi-language support with RTL support
- **Performance**: Virtualized message lists, lazy loading, optimistic updates
- **Testing**: Comprehensive test suite with Vitest and Playwright

### Backend (Python FastAPI)
- **Secure Authentication**: JWT tokens with bcrypt password hashing
- **Real-time Messaging**: WebSocket communication with presence management
- **End-to-End Encryption**: RSA + AES encryption for message security
- **File Transfer**: Secure file upload with size limits and validation
- **Database**: MongoDB with Beanie ODM for data persistence
- **Message Acknowledgments**: Delivery receipts and retry logic
- **Presence System**: Online/offline status with typing indicators

## 🏗️ Architecture

### Frontend Stack
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State Management**: Zustand + React Query
- **Forms**: react-hook-form + Zod validation
- **Real-time**: WebSocket client
- **Testing**: Vitest + React Testing Library + Playwright
- **i18n**: next-intl

### Backend Stack
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Database**: MongoDB with Beanie ODM
- **Real-time**: WebSockets
- **Security**: JWT, bcrypt, RSA, AES-256-CBC
- **Caching**: Redis
- **File Storage**: Local filesystem (configurable)

## 📦 Installation

### Prerequisites
- Node.js 18+ and npm/pnpm
- Python 3.11+
- MongoDB 6.0+
- Redis (optional, for presence management)

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. **Start MongoDB**:
   ```bash
   # macOS with Homebrew
   brew services start mongodb-community
   
   # Ubuntu/Debian
   sudo systemctl start mongod
   ```

6. **Start the backend**:
   ```bash
   ./start.sh
   # Or manually: python run.py
   ```

The backend will be available at:
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/{user_id}/{session_id}

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd ..  # If you're in backend directory
   ```

2. **Install dependencies**:
   ```bash
   npm install
   # or
   pnpm install
   ```

3. **Start development server**:
   ```bash
   npm run dev
   # or
   pnpm dev
   ```

The frontend will be available at http://localhost:3000

## 🔧 Configuration

### Backend Environment Variables

Create a `.env` file in the `backend` directory:

```env
# Database
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=messaging_app

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis (optional)
REDIS_URL=redis://localhost:6379

# File Upload
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_FILE_TYPES=image/*,video/*,audio/*,.pdf,.doc,.docx,.txt

# Server
HOST=0.0.0.0
PORT=8000
```

### Frontend Environment Variables

Create a `.env.local` file in the root directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 🚀 Quick Start

1. **Start MongoDB**:
   ```bash
   brew services start mongodb-community
   ```

2. **Start Backend** (in one terminal):
   ```bash
   cd backend
   ./start.sh
   ```

3. **Start Frontend** (in another terminal):
   ```bash
   npm run dev
   ```

4. **Open your browser**:
   - Frontend: http://localhost:3000
   - Backend API docs: http://localhost:8000/docs

## 🧪 Testing

### Frontend Tests
```bash
# Unit tests
npm run test

# E2E tests
npm run e2e

# All tests
npm run ci
```

### Backend Tests
```bash
cd backend
python -m pytest
```

## 📱 Usage

### Authentication
1. Visit http://localhost:3000
2. Sign up with a new account or use demo credentials
3. You'll be redirected to the main messaging interface

### Messaging
1. **Start a conversation**: Click "New Message" or use the command palette (⌘K)
2. **Send messages**: Type in the composer and press Enter
3. **Real-time updates**: Messages appear instantly via WebSocket
4. **File sharing**: Click the paperclip icon to attach files
5. **Reactions**: Click on messages to add emoji reactions

### Keyboard Shortcuts
- `⌘K` / `Ctrl+K`: Open command palette
- `Enter`: Send message (configurable)
- `Shift+Enter`: New line (configurable)
- `↑/↓`: Navigate conversation list
- `Esc`: Close modals, return to composer

## 🔒 Security Features

### Authentication & Authorization
- JWT-based authentication with secure token storage
- Password hashing with bcrypt and salt
- Session management with device tracking
- Role-based permissions for conversations

### Message Security
- End-to-end encryption using RSA + AES-256-CBC
- Message integrity verification with SHA-256
- Secure key exchange protocol
- Encrypted file storage

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF protection
- Rate limiting on API endpoints

### File Security
- File type validation
- Size limits (configurable)
- Virus scanning (extensible)
- Secure file storage with access controls

## 🌐 API Documentation

### Authentication Endpoints
- `POST /api/auth/signup` - User registration
- `POST /api/auth/signin` - User login
- `POST /api/auth/signout` - User logout
- `GET /api/auth/me` - Get current user

### Conversation Endpoints
- `GET /api/conversations` - List conversations
- `POST /api/conversations` - Create conversation
- `GET /api/conversations/{id}` - Get conversation details
- `PUT /api/conversations/{id}` - Update conversation
- `DELETE /api/conversations/{id}` - Delete conversation

### Message Endpoints
- `GET /api/conversations/{id}/messages` - Get messages
- `POST /api/conversations/{id}/messages` - Send message
- `PUT /api/messages/{id}` - Edit message
- `DELETE /api/messages/{id}` - Delete message
- `POST /api/messages/{id}/reactions` - Add reaction

### WebSocket Events
- `message` - Send message
- `typing_start` / `typing_stop` - Typing indicators
- `presence_update` - User status changes
- `message_ack` - Message acknowledgment
- `reaction` - Add/remove reactions

## 🛠️ Development

### Project Structure
```
messaging-app/
├── src/                    # Frontend source
│   ├── app/               # Next.js app router
│   ├── components/        # React components
│   ├── services/          # API and WebSocket services
│   ├── store/             # Zustand stores
│   ├── types/             # TypeScript types
│   └── lib/               # Utilities
├── backend/               # Backend source
│   ├── app/               # FastAPI application
│   │   ├── models/        # Database models
│   │   ├── routes/        # API routes
│   │   ├── security/      # Security utilities
│   │   └── websockets/    # WebSocket handlers
│   └── requirements.txt   # Python dependencies
└── README.md
```

### Adding New Features

1. **Backend**: Add new routes in `backend/app/routes/`
2. **Frontend**: Create components in `src/components/`
3. **Types**: Update TypeScript types in `src/types/`
4. **API**: Add API methods in `src/services/api.ts`
5. **Tests**: Write tests for new functionality

### Code Style
- **Frontend**: ESLint + Prettier with accessibility rules
- **Backend**: Black + isort for Python formatting
- **Commits**: Conventional commits with commitlint
- **Pre-commit**: Husky hooks for linting and formatting

## 🚀 Deployment

### Backend Deployment
1. Set up MongoDB and Redis in production
2. Configure environment variables
3. Use a WSGI server like Gunicorn with Uvicorn workers
4. Set up reverse proxy with Nginx
5. Enable HTTPS with SSL certificates

### Frontend Deployment
1. Build the application: `npm run build`
2. Deploy to Vercel, Netlify, or your preferred platform
3. Configure environment variables
4. Set up custom domain and HTTPS

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Next.js](https://nextjs.org/) for the React framework
- [FastAPI](https://fastapi.tiangolo.com/) for the Python backend
- [Tailwind CSS](https://tailwindcss.com/) for styling
- [shadcn/ui](https://ui.shadcn.com/) for UI components
- [MongoDB](https://www.mongodb.com/) for the database
- [WebSockets](https://websockets.readthedocs.io/) for real-time communication

## 📞 Support

For support, email support@messagingapp.com or create an issue in the GitHub repository.

---

**Happy Messaging! 🚀**