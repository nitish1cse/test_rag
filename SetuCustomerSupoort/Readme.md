# Setu Customer Support Documentation System

A FastAPI-based system for managing and querying Setu's product documentation from multiple sources including Confluence and web URLs. The system uses ChromaDB for vector storage and OpenAI for embeddings and question answering.

## Features

- **Multi-source Document Management**
  - Confluence document integration
  - Web URL content crawling with recursive link following
  - Document version tracking and change detection

- **Advanced Search & QA**
  - Vector-based semantic search using ChromaDB
  - GPT-powered question answering
  - Context-aware responses with source attribution

- **Product Organization**
  - Product-based document organization
  - Automatic document categorization
  - Document statistics and tracking

## Setup

### Prerequisites

- Python 3.10 or higher
- Virtual environment (recommended)
- Confluence API access
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd SetuCustomerSupoort
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create necessary directories:
```bash
mkdir -p data chroma_db config
```

### Configuration

1. Configure OpenAI API key:
```bash
curl -X POST "http://localhost:8000/openai/api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-openai-api-key"
  }'
```

2. Configure Confluence credentials:
```bash
curl -X POST "http://localhost:8000/confluence/config" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "your-confluence-url",
    "username": "your-username",
    "api_token": "your-api-token"
  }'
```

## Usage

### Starting the Server

```bash
uvicorn main:app --reload
```

### Managing Confluence Documents

1. Store Confluence documents:
```bash
curl -X POST "http://localhost:8000/confluence/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "AA",
    "document_ids": ["page-id-1", "page-id-2"]
  }'
```

2. Check document statistics:
```bash
curl "http://localhost:8000/confluence/documents/AA"
```

### Managing Web URLs

1. Store URL content:
```bash
curl -X POST "http://localhost:8000/url/store" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "AA",
    "urls": [
      "https://docs.example.com/aa/guide"
    ]
  }'
```

2. Check URL statistics:
```bash
curl "http://localhost:8000/url/stats/AA"
```

### Using the QA System

Ask questions about stored documentation:
```bash
curl -X POST "http://localhost:8000/qa/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "AA",
    "question": "What are common reasons for FIP_DENIED errors?"
  }'
```

## Project Structure



## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Error Handling

The system includes comprehensive error handling:
- Input validation
- API error handling
- Document processing errors
- Storage and retrieval errors

## Security

- API keys and credentials are securely stored
- Rate limiting for external APIs
- Input validation and sanitization
- Domain restrictions for URL crawling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]

## Support

For support, please contact [your contact information]