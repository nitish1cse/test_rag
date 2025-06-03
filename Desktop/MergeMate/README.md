# AI MergeMate

An AI-powered code review assistant that integrates with GitLab Merge Requests and Jira to provide intelligent, automated code reviews.

## Features

- 🤖 AI-powered code review using OpenAI GPT-4, Anthropic Claude, or Ollama
- 🔄 GitLab Merge Request integration
- 🎫 Jira ticket context integration
- ⚡ Fast and automated reviews
- 🔒 Secure token handling
- 🐳 Docker support

## Prerequisites

- Python 3.9+
- Docker (optional)
- GitLab account with API access
- Jira account with API access
- OpenAI API key or Anthropic API key

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/merge-mate.git
cd merge-mate
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```bash
cp .env.example .env
```

5. Configure your environment variables in `.env`:
```env
# API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# GitLab Configuration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_gitlab_token

# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@domain.com
JIRA_API_TOKEN=your_jira_token

# Server Configuration
HOST=192.168.1.108
PORT=8000
```

## Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload
```

### Docker

```bash
docker build -t merge-mate .
docker run -p 8000:8000 merge-mate
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Webhook Setup

1. In your GitLab project settings, go to Webhooks
2. Add a new webhook with URL: `https://your-domain.com/gitlab-hook`
3. Select "Merge request events"
4. Add your secret token to the `.env` file as `GITLAB_WEBHOOK_SECRET`

## Testing

```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details 