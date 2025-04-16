const API_BASE_URL = 'http://localhost:8000';

// Generic API request handler
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ data?: T; error?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'An error occurred');
    }

    return { data };
  } catch (error) {
    console.error('API Error:', error);
    return { error: error instanceof Error ? error.message : 'An error occurred' };
  }
}

// OpenAI API Service
export const openaiService = {
  setApiKey: (apiKey: string) =>
    apiRequest<{ message: string }>('/openai/api-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    }),

  validateApiKey: () =>
    apiRequest<{ is_valid: boolean }>('/openai/validate-key', {
      method: 'GET',
    }),
};

// Confluence Service
export const confluenceService = {
  configureConfluence: (config: {
    url: string;
    username: string;
    api_token: string;
  }) =>
    apiRequest<{ message: string }>('/confluence/config', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
};

// Chat Service
export const chatService = {
  sendMessage: (product: string, question: string) =>
    apiRequest<{
      answer: string;
      sources: Array<{
        title: string;
        page_id: string;
        type: string;
        product: string;
      }>;
      previous_feedback: Array<any>;
    }>('/qa/ask', {
      method: 'POST',
      body: JSON.stringify({ product, question }),
    }),
  
  // New function for streaming API requests
  streamMessage: async (product: string, question: string, onChunk: (chunk: string) => void, onComplete: (sources: any[]) => void) => {
    try {
      const response = await fetch(`${API_BASE_URL}/qa/ask/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product, question }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'An error occurred');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body cannot be read');

      let sources: any[] = [];
      let accumulated = '';
      
      // Process the stream
      const processStream = async (): Promise<void> => {
        const { done, value } = await reader.read();
        
        if (done) {
          // When all chunks are processed, finalize
          onComplete(sources);
          return;
        }
        
        // Convert bytes to text
        const text = new TextDecoder().decode(value);
        
        // Special case handling for JSON chunks
        try {
          // Check for pure JSON response (for error cases or empty results)
          if (text.trim().startsWith('{') && text.trim().endsWith('}')) {
            try {
              // Try to parse as pure JSON
              const jsonData = JSON.parse(text);
              
              // If it has 'sources' key, it's metadata
              if ('sources' in jsonData) {
                sources = jsonData.sources || [];
                return processStream();
              }
            } catch {
              // Not valid JSON or not our expected format, continue normal processing
            }
          }
          
          // Regular JSON detection within text
          if (text.includes('{"sources":')) {
            const jsonStartIndex = text.indexOf('{"sources":');
            if (jsonStartIndex !== -1) {
              // Extract everything before the JSON as content
              const contentPart = text.substring(0, jsonStartIndex);
              if (contentPart) {
                accumulated += contentPart;
                onChunk(contentPart);
              }
              
              // Parse the JSON part
              const jsonPart = text.substring(jsonStartIndex);
              try {
                const metadataObj = JSON.parse(jsonPart);
                sources = metadataObj.sources || [];
              } catch (e) {
                console.error('Error parsing JSON metadata:', e);
              }
              
              // Continue processing without adding the JSON to accumulated
              return processStream();
            }
          }
          
          // If no JSON detected, treat as normal content
          accumulated += text;
          onChunk(text);
        } catch (e) {
          // If any error occurs, treat as normal content
          console.error('Error processing stream chunk:', e);
          accumulated += text;
          onChunk(text);
        }
        
        // Continue reading
        return processStream();
      };
      
      return processStream();
    } catch (error) {
      console.error('Streaming Error:', error);
      throw error;
    }
  },
};

// Product Service
export const productService = {
  getProducts: () =>
    apiRequest<string[]>('/config/products', {
      method: 'GET',
    }),

  validateProduct: (product: string) =>
    apiRequest<{ 
      product: string;
      document_count: number;
      status: string;
    }>(`/confluence/documents/${product}`, {
      method: 'GET',
    }),
};

// Document Service
export const documentService = {
  storeConfluenceDocs: (product: string, documentIds: string[]) =>
    apiRequest<{ message: string }>('/confluence/documents', {
      method: 'POST',
      body: JSON.stringify({ product, document_ids: documentIds }),
    }),

  storeUrls: (product: string, urls: string[]) =>
    apiRequest<{ message: string }>('/url/store', {
      method: 'POST',
      body: JSON.stringify({ product, urls }),
    }),

  getDocumentStats: (product: string) =>
    apiRequest<{ document_count: number; status: string }>(`/confluence/documents/${product}`, {
      method: 'GET',
    }),
};

// Server Status Service
export const serverService = {
  checkStatus: () =>
    apiRequest<{ status: string }>('/', {
      method: 'GET',
    }),
};