# PLC Code Generator API

A FastAPI-based service that generates PLC code from natural language specifications.

## Features

- Generate PLC code for multiple vendors (Siemens, Rockwell, Beckhoff)
- Auto-detection of vendor from specification text
- RESTful API for easy integration
- Swagger UI documentation at `/docs`

## API Endpoints

- `POST /generate_code` - Generate PLC code from specification
- `GET /health` - Health check endpoint

## Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables (create a `.env` file):
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```
4. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

## Deployment to Railway

1. Install the Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```
2. Login to Railway:
   ```bash
   railway login
   ```
3. Link your project:
   ```bash
   railway link
   ```
4. Set environment variables:
   ```bash
   railway env set OPENAI_API_KEY=your_openai_api_key
   ```
5. Deploy:
   ```bash
   railway up
   ```

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `PORT` - Port to run the server on (default: 8000)

## License

MIT
