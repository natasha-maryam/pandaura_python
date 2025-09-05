# Pandura Chat

A real-time chat application with AI capabilities using FastAPI, WebSockets, and OpenAI's GPT models.

## Features

- Real-time chat interface using WebSockets
- Conversation memory using LangChain
- Support for different OpenAI models
- CORS enabled for frontend integration
- Environment variable configuration

## Prerequisites

- Python 3.8 or higher
- OpenAI API key
- pip (Python package manager)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pandura-chat
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your OpenAI API key:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   MODEL_NAME=gpt-4o-mini  # or any other supported model
   ```

## Running the Application

### Development Server

You can run the application in two ways:

1. **Using uvicorn directly** (recommended for development with auto-reload):
   ```bash
   uvicorn web:app --reload
   ```

2. **Directly with Python** (simpler but without auto-reload):
   ```bash
   python3 web.py
   ```

   Note: When running with `python3 web.py`, the server will start on `http://0.0.0.0:8000`

The server will start at `http://localhost:8000`

### Production Server

For production, use a production ASGI server like uvicorn with multiple workers:

```bash
uvicorn web:app --host 0.0.0.0 --port 8000 --workers 4
```

## WebSocket Endpoint

The WebSocket endpoint is available at:
```
ws://localhost:8000/ws
```

### WebSocket Message Format

Send messages as JSON:
```json
{
    "message": "Your message here"
 }
```

## API Documentation

Once the server is running, you can access:

- Interactive API documentation: http://localhost:8000/docs
- Alternative API documentation: http://localhost:8000/redoc

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes | - |
| `MODEL_NAME` | OpenAI model to use | No | `gpt-4o-mini` |

## Project Structure

```
pandura-chat/
├── .env                    # Environment variables
├── web.py                 # Main FastAPI application
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Testing

To test the WebSocket connection, you can use a WebSocket client like [Postman](https://www.postman.com/) or [websocat](https://github.com/vi/websocat):

```bash
# Using websocat
echo '{"message": "Hello, world!"}' | websocat ws://localhost:8000/ws
```

## Frontend Integration

To connect from a frontend application, use the WebSocket API:

```javascript
const socket = new WebSocket('ws://localhost:8000/ws');

socket.onopen = () => {
  console.log('Connected to WebSocket');
  socket.send(JSON.stringify({
    message: 'Hello, server!',
    session_id: 'user_123'  // Optional: for conversation history
  }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

socket.onclose = () => {
  console.log('Disconnected from WebSocket');
};
```

## Deployment

### Using Railway

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```

2. Link your project:
   ```bash
   railway login
   railway link
   ```

3. Set environment variables:
   ```bash
   railway env set OPENAI_API_KEY=your_openai_api_key
   ```

4. Deploy:
   ```bash
   railway up
   ```

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t pandura-chat .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 --env-file .env pandura-chat
   ```

## Troubleshooting

- **Connection refused**: Make sure the server is running and the port is correct
- **Invalid API key**: Verify your OpenAI API key in the `.env` file
- **Module not found**: Run `pip install -r requirements.txt`


