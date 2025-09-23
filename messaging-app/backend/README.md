# Secure Messaging App Backend

A comprehensive, secure real-time messaging application backend built with FastAPI, MongoDB, and WebSockets. Features end-to-end encryption, robust authentication, and scalable architecture.

## 🚀 Features

### Security & Authentication
- **JWT-based authentication** with access and refresh tokens
- **Password hashing** using bcrypt with salt
- **Session management** with device tracking
- **Rate limiting** to prevent abuse
- **Input validation** and sanitization
- **Magic link** passwordless authentication

### Real-time Communication
- **WebSocket connections** for real-time messaging
- **Message acknowledgments** and delivery status
- **Typing indicators** and presence updates
- **Connection heartbeat** monitoring
- **Automatic reconnection** handling

### End-to-End Encryption
- **RSA key pairs** for user authentication
- **AES-256-CBC** for message encryption
- **Key exchange protocols** for secure communication
- **Message signing** for integrity verification
- **File encryption** for attachments

### Database & Storage
- **MongoDB** with Beanie ODM for flexible schema
- **Optimized indexes** for fast queries
- **Embedded documents** for better performance
- **Connection pooling** and async operations

### File Handling
- **Secure file upload** with size limits
- **File type validation** and scanning
- **Encrypted file storage** with integrity checks
- **Thumbnail generation** for images
- **Progress tracking** for uploads

## 🏗️ Architecture

```
backend/
├── app/
│   ├── models/          # MongoDB models with Beanie
│   ├── routes/          # FastAPI route handlers
│   ├── websockets/      # WebSocket connection management
│   ├── security/        # Authentication and encryption
│   ├── database.py      # Database configuration
│   └── main.py          # FastAPI application
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🔧 Installation

### Prerequisites
- Python 3.11+
- MongoDB 5.0+
- Redis (optional, for distributed caching)

### Setup

1. **Clone and navigate to backend directory:**
```bash
cd backend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Start MongoDB:**
```bash
mongod
```

6. **Run the application:**
```bash
python -m app.main
```

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Database
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=messaging_app

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption
ENCRYPTION_KEY=your-32-character-encryption-key

# Redis (optional)
REDIS_URL=redis://localhost:6379

# File Upload
MAX_FILE_SIZE=104857600  # 100MB
ALLOWED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf

# WebSocket
WS_HEARTBEAT_INTERVAL=30
WS_CONNECTION_TIMEOUT=300

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/signin` - Sign in user
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/magic-link` - Send magic link
- `POST /api/auth/change-password` - Change password
- `POST /api/auth/signout` - Sign out user
- `GET /api/auth/me` - Get current user

### Users
- `GET /api/users` - List users
- `GET /api/users/{user_id}` - Get user details
- `PUT /api/users/{user_id}` - Update user profile
- `POST /api/users/{user_id}/avatar` - Upload avatar

### Conversations
- `GET /api/conversations` - List user conversations
- `POST /api/conversations` - Create conversation
- `GET /api/conversations/{conversation_id}` - Get conversation details
- `PUT /api/conversations/{conversation_id}` - Update conversation
- `DELETE /api/conversations/{conversation_id}` - Delete conversation
- `POST /api/conversations/{conversation_id}/participants` - Add participant
- `DELETE /api/conversations/{conversation_id}/participants/{user_id}` - Remove participant

### Messages
- `GET /api/conversations/{conversation_id}/messages` - Get messages
- `POST /api/conversations/{conversation_id}/messages` - Send message
- `PUT /api/messages/{message_id}` - Edit message
- `DELETE /api/messages/{message_id}` - Delete message
- `POST /api/messages/{message_id}/reactions` - Add reaction
- `DELETE /api/messages/{message_id}/reactions/{emoji}` - Remove reaction

### Files
- `POST /api/files/upload` - Upload file
- `GET /api/files/{file_id}` - Get file
- `DELETE /api/files/{file_id}` - Delete file

## 🔌 WebSocket Endpoints

### Private WebSocket
```
ws://localhost:8000/ws/{user_id}/{session_id}
```

**Message Types:**
- `ping` - Keep connection alive
- `message` - Send message
- `typing_start` - Start typing indicator
- `typing_stop` - Stop typing indicator
- `message_ack` - Acknowledge message
- `message_read` - Mark message as read
- `reaction` - Add/remove reaction
- `presence_update` - Update user presence
- `key_exchange` - Exchange encryption keys

### Public WebSocket
```
ws://localhost:8000/ws/public/{channel}
```

**Message Types:**
- `subscribe` - Subscribe to channel
- `announcement` - System announcements

## 🔐 Security Features

### Authentication & Authorization
- JWT tokens with configurable expiration
- Refresh token rotation
- Session management with device tracking
- Password strength validation
- Account lockout protection

### Encryption
- End-to-end message encryption
- RSA key pairs for user authentication
- AES-256-CBC for symmetric encryption
- Secure key exchange protocols
- Message integrity verification

### Input Validation
- SQL injection prevention
- XSS protection
- File upload validation
- Rate limiting
- Input sanitization

### Network Security
- CORS configuration
- HTTPS enforcement (in production)
- WebSocket security
- Connection timeout handling

## 📊 Database Schema

### Users Collection
```json
{
  "_id": "user_id",
  "email": "user@example.com",
  "username": "username",
  "display_name": "Display Name",
  "password_hash": "hashed_password",
  "salt": "random_salt",
  "status": "online|away|offline|dnd",
  "last_seen": "2024-01-10T10:00:00Z",
  "public_key": "RSA_public_key",
  "private_key_encrypted": "encrypted_private_key",
  "created_at": "2024-01-10T10:00:00Z",
  "updated_at": "2024-01-10T10:00:00Z"
}
```

### Conversations Collection
```json
{
  "_id": "conversation_id",
  "name": "Conversation Name",
  "conversation_type": "dm|group|channel",
  "participant_ids": ["user1", "user2"],
  "last_message_id": "message_id",
  "last_activity": "2024-01-10T10:00:00Z",
  "message_count": 42,
  "created_at": "2024-01-10T10:00:00Z"
}
```

### Messages Collection
```json
{
  "_id": "message_id",
  "conversation_id": "conversation_id",
  "sender_id": "user_id",
  "content": "Message content",
  "message_type": "text|image|file|system",
  "status": "sending|sent|delivered|read|failed",
  "encrypted_content": "encrypted_message",
  "encryption_iv": "initialization_vector",
  "attachments": [{"file_name": "file.jpg", "file_size": 1024}],
  "reactions": [{"user_id": "user1", "emoji": "👍"}],
  "created_at": "2024-01-10T10:00:00Z"
}
```

## 🚀 Deployment

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "-m", "app.main"]
```

### Environment Variables for Production
```env
MONGODB_URL=mongodb://mongodb:27017
REDIS_URL=redis://redis:6379
SECRET_KEY=your-production-secret-key
ENCRYPTION_KEY=your-production-encryption-key
```

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py
```

## 📈 Monitoring & Logging

- Structured logging with timestamps
- Connection monitoring
- Performance metrics
- Error tracking
- Rate limit monitoring

## 🔧 Development

### Code Style
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API examples

## 🔮 Roadmap

- [ ] Voice and video calling
- [ ] Message threading
- [ ] Advanced search
- [ ] Bot integration
- [ ] Mobile push notifications
- [ ] Message scheduling
- [ ] Advanced encryption options
- [ ] Multi-language support
