import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Grid,
  Alert,
  Tabs,
  Tab,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
} from '@mui/material';
import { productService, documentService } from '../services/api';

export const DocumentManager: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [products, setProducts] = useState<string[]>([]);

  // Confluence Documents state
  const [confProduct, setConfProduct] = useState('');
  const [confDocIds, setConfDocIds] = useState('');

  // URL Documents state
  const [urlProduct, setUrlProduct] = useState('');
  const [urls, setUrls] = useState('');

  // Document Stats state
  const [statsProduct, setStatsProduct] = useState('');
  const [docStats, setDocStats] = useState<{
    document_count: number;
    status: string;
  } | null>(null);
  
  // GitHub Repository state
  const [githubRepoUrl, setGithubRepoUrl] = useState('');
  const [githubFolders, setGithubFolders] = useState('');
  const [githubToken, setGithubToken] = useState('');

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
      }
    }
  };

  const handleStoreConfluenceDocs = async () => {
    if (!confProduct || !confDocIds.trim()) return;

    setLoading(true);
    const response = await documentService.storeConfluenceDocs(
      confProduct,
      confDocIds.split(',').map(id => id.trim())
    );
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Documents stored successfully');
      setConfDocIds('');
    }
  };

  const handleStoreUrls = async () => {
    if (!urlProduct || !urls.trim()) return;

    setLoading(true);
    const response = await documentService.storeUrls(
      urlProduct,
      urls.split(',').map(url => url.trim())
    );
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'URLs stored successfully');
      setUrls('');
    }
  };
  
  const handleFetchGithubContent = async () => {
    if (!githubRepoUrl.trim() || !githubFolders.trim()) return;
    
    setLoading(true);
    const response = await documentService.fetchGithubContent(
      githubRepoUrl.trim(),
      githubFolders.trim(),
      githubToken.trim() || undefined
    );
    setLoading(false);
    
    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'GitHub content fetched successfully');
      // Don't clear the fields to allow multiple fetches from same repo
    }
  };

  const getDocumentStats = async () => {
    if (!statsProduct) return;

    setLoading(true);
    const response = await documentService.getDocumentStats(statsProduct);
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
      setDocStats(null);
    } else {
      setDocStats(response.data || null);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="Confluence Documents" />
        <Tab label="URL Documents" />
        <Tab label="GitHub Repository" />
        <Tab label="Document Statistics" />
      </Tabs>

      {tabValue === 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Add Confluence Documents
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                label="Select Product"
                value={confProduct}
                onChange={(e) => setConfProduct(e.target.value)}
              >
                {products.map((product) => (
                  <MenuItem key={product} value={product}>{product}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={4}
                label="Document IDs (comma-separated)"
                placeholder="e.g., 123456, 789012"
                value={confDocIds}
                onChange={(e) => setConfDocIds(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleStoreConfluenceDocs}
                disabled={loading || !confProduct || !confDocIds.trim()}
              >
                {loading ? <CircularProgress size={24} /> : 'Store Confluence Documents'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {tabValue === 1 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Add URL Documents
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                label="Select Product"
                value={urlProduct}
                onChange={(e) => setUrlProduct(e.target.value)}
              >
                {products.map((product) => (
                  <MenuItem key={product} value={product}>{product}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={4}
                label="URLs (comma-separated)"
                placeholder="e.g., https://example.com/doc1, https://example.com/doc2"
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleStoreUrls}
                disabled={loading || !urlProduct || !urls.trim()}
              >
                {loading ? <CircularProgress size={24} /> : 'Store URLs'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}
      
      {tabValue === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Import From GitHub Repository
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="GitHub Repository URL"
                placeholder="e.g., https://github.com/SetuHQ/docs"
                value={githubRepoUrl}
                onChange={(e) => setGithubRepoUrl(e.target.value)}
                helperText="Enter the GitHub repository URL containing Setu documentation"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Folders to Fetch (comma-separated)"
                placeholder="e.g., content, content/payments, content/data"
                value={githubFolders}
                onChange={(e) => setGithubFolders(e.target.value)}
                helperText="Specify which folders to fetch MDX files from"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="GitHub Token (Optional)"
                placeholder="ghp_xxxxxxxxxx"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                helperText="Provide a GitHub token to avoid rate limits (optional but recommended)"
                type="password"
              />
            </Grid>
            <Grid item xs={12}>
              <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                This will automatically fetch all .mdx files from the specified folders and detect the appropriate product for each file. The detection is based on file structure and content analysis.
              </Typography>
              <Button
                variant="contained"
                onClick={handleFetchGithubContent}
                disabled={loading || !githubRepoUrl.trim() || !githubFolders.trim()}
              >
                {loading ? <CircularProgress size={24} /> : 'Fetch GitHub Content'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {tabValue === 3 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Document Statistics
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                label="Select Product"
                value={statsProduct}
                onChange={(e) => setStatsProduct(e.target.value)}
              >
                {products.map((product) => (
                  <MenuItem key={product} value={product}>{product}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={getDocumentStats}
                disabled={loading || !statsProduct}
              >
                {loading ? <CircularProgress size={24} /> : 'Get Statistics'}
              </Button>
            </Grid>
          </Grid>

          {docStats && (
            <TableContainer sx={{ mt: 3 }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Product</TableCell>
                    <TableCell>Document Count</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>{statsProduct}</TableCell>
                    <TableCell>{docStats.document_count}</TableCell>
                    <TableCell>{docStats.status}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      )}

      {status && (
        <Alert
          severity={status.toLowerCase().includes('error') ? 'error' : 'success'}
          sx={{ mt: 3 }}
          onClose={() => setStatus(null)}
        >
          {status}
        </Alert>
      )}
    </Box>
  );
};