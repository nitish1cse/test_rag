import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  MenuItem,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import RefreshIcon from '@mui/icons-material/Refresh';
import { chatService, productService } from '../services/api';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{
    title: string;
    page_id: string;
    type: string;
    product: string;
  }>;
}

export const Chat: React.FC = () => {
  const [input, setInput] = useState('');
  const [product, setProduct] = useState('');
  const [products, setProducts] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemMessage, setSystemMessage] = useState<string>('Select a product to start chatting');

  useEffect(() => {
    loadProducts();
  }, []);

  const loadProducts = async () => {
    setLoading(true);
    const response = await productService.getProducts();
    setLoading(false);

    if (response.data) {
      setProducts(response.data);
    } else {
      // Fallback to loading from public/product_docs.json
      try {
        const fileResponse = await fetch('/product_docs.json');
        const data = await fileResponse.json();
        setProducts(Object.keys(data));
      } catch (error) {
        console.error('Error loading products:', error);
        setError('Failed to load products');
      }
    }
  };

  const handleProductChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedProduct = e.target.value;
    setProduct(selectedProduct);

    if (selectedProduct) {
      setLoading(true);
      const response = await productService.validateProduct(selectedProduct);
      setLoading(false);

      if (response.error) {
        setSystemMessage(`Warning: ${response.error}`);
      } else {
        const status = response.data?.status || 'unknown';
        const documentCount = response.data?.document_count || 0;
        
        if (status === 'active' && documentCount > 0) {
          setSystemMessage(`Selected ${selectedProduct}: ${documentCount} documents available`);
        } else if (status === 'empty' || documentCount === 0) {
          setSystemMessage(`Warning: No documents found for ${selectedProduct}. Please add documents first.`);
        } else {
          setSystemMessage(`Selected product: ${selectedProduct} (${status})`);
        }
      }
    } else {
      setSystemMessage('Select a product to start chatting');
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !product || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    const currentMessages = [...messages, userMessage];
    setMessages(currentMessages);

    const userInput = input;
    setInput('');
    setLoading(true);
    setError(null);
    setSystemMessage('Processing your question...');

    try {
      // Use non-streaming API
      const response = await chatService.sendMessage(product, userInput);

      if (response.error) {
        setError(response.error);
        setSystemMessage('Error: Failed to get response');
      } else {
        // Check if response indicates no documentation
        const isNoDocsResponse = response.data?.answer.includes("No documentation found for product") || 
                               response.data?.answer.includes("I don't have enough information about");

        if (isNoDocsResponse) {
          // Format a better no-docs response
          const formattedResponse = `## No Information Found

I don't have any information about '${product}' to answer your question.

Please try:
- Checking if you selected the correct product
- Adding documentation for this product first
- Asking about a different topic

If you believe this is an error, please contact support.`;

          setMessages([
            ...currentMessages,
            { 
              role: 'assistant', 
              content: formattedResponse,
              sources: []
            }
          ]);
        } else {
          // Regular response with possible sources
          setMessages([
            ...currentMessages,
            { 
              role: 'assistant', 
              content: response.data?.answer || 'No answer provided',
              sources: response.data?.sources || []
            }
          ]);
        }
        setSystemMessage('Ready for next question');
      }
    } catch (error) {
      console.error("Error during request:", error);
      setError('Failed to get response from server');
      setSystemMessage('Error: Server communication issue');
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setSystemMessage('Chat cleared. Select a product to start chatting');
  };

  // Render markdown with code highlighting
  const renderMarkdown = (content: string) => {
    return (
      <ReactMarkdown
        components={{
          code({ node, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return !props.inline && match ? (
              <SyntaxHighlighter
                style={materialLight}
                language={match[1]}
                PreTag="div"
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className={className} {...props}>
                {children}
              </code>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 3, minHeight: '70vh', display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" gutterBottom>
          Chat with Setu Assistant
        </Typography>

        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          <TextField
            select
            label="Select Product"
            value={product}
            onChange={handleProductChange}
            fullWidth
          >
            {products.map((p) => (
              <MenuItem key={p} value={p}>{p}</MenuItem>
            ))}
          </TextField>

          <IconButton onClick={loadProducts} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Box>

        <Paper
          elevation={0}
          sx={{
            bgcolor: '#e3f2fd',
            p: 2,
            mb: 2,
            borderRadius: 1,
            color: product ? 'text.primary' : 'text.secondary'
          }}
        >
          <Typography variant="body2">
            {systemMessage}
          </Typography>
        </Paper>

        <Box
          sx={{
            flex: 1,
            mb: 2,
            p: 2,
            bgcolor: '#f5f5f5',
            borderRadius: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          {messages.map((msg, index) => (
            <Box
              key={index}
              sx={{
                p: 2,
                bgcolor: msg.role === 'user' ? '#e3f2fd' : 'white',
                borderRadius: 2,
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
              }}
            >
              {msg.role === 'user' ? (
                <Typography>{msg.content}</Typography>
              ) : (
                <>
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="subtitle2" color="primary">
                      Setu Assistant
                    </Typography>
                  </Box>
                  <Box sx={{ fontSize: '0.9rem' }}>
                    {renderMarkdown(msg.content || '')}
                  </Box>
                  {msg.sources && msg.sources.length > 0 ? (
                    <Box sx={{ mt: 2, fontSize: '0.75rem', color: 'text.secondary' }}>
                      <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                        Sources:
                      </Typography>
                      <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                        {msg.sources.map((source, idx) => (
                          <li key={idx}>
                            {source.title} ({source.type})
                          </li>
                        ))}
                      </ul>
                    </Box>
                  ) : msg.content && msg.content.includes("No Information Found") ? (
                    <Box sx={{ mt: 2, fontSize: '0.75rem', color: 'warning.main', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                        No documentation found for this product
                      </Typography>
                    </Box>
                  ) : null}
                </>
              )}
            </Box>
          ))}

          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={loading || !product}
          />
          <Button
            variant="contained"
            color="primary"
            endIcon={<SendIcon />}
            onClick={handleSend}
            disabled={!input.trim() || !product || loading}
          >
            Send
          </Button>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
          <Button
            variant="outlined"
            color="warning"
            onClick={handleClearChat}
            disabled={messages.length === 0}
          >
            Clear Chat
          </Button>

          <Typography variant="caption" color="text.secondary">
            Status: {loading ? 'Processing...' : 'Ready'}
          </Typography>
        </Box>

        {error && (
          <Alert
            severity="error"
            sx={{ mt: 2 }}
            onClose={() => setError(null)}
          >
            {error}
          </Alert>
        )}
      </Paper>
    </Box>
  );
};