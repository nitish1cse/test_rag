import React, { useState } from 'react';
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
  CircularProgress,
} from '@mui/material';
import { openaiService, confluenceService } from '../services/api';

export const ConfigurationPanel: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  // OpenAI config
  const [apiKey, setApiKey] = useState('');

  // Confluence config
  const [confluenceUrl, setConfluenceUrl] = useState('');
  const [confluenceUsername, setConfluenceUsername] = useState('');
  const [confluenceToken, setConfluenceToken] = useState('');

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) return;

    setLoading(true);
    const response = await openaiService.setApiKey(apiKey);
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'API key configured successfully');
      setApiKey('');
    }
  };

  const handleSaveConfluence = async () => {
    if (!confluenceUrl.trim() || !confluenceUsername.trim() || !confluenceToken.trim()) return;

    setLoading(true);
    const response = await confluenceService.configureConfluence({
      url: confluenceUrl,
      username: confluenceUsername,
      api_token: confluenceToken,
    });
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Confluence configured successfully');
      // Don't clear the fields as they're often reused
    }
  };

  const handleValidateApiKey = async () => {
    setLoading(true);
    const response = await openaiService.validateApiKey();
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.is_valid ? 'API key is valid' : 'API key is invalid');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="OpenAI Configuration" />
        <Tab label="Confluence Configuration" />
      </Tabs>

      {tabValue === 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            OpenAI Configuration
          </Typography>

          <TextField
            fullWidth
            type="password"
            placeholder="OpenAI API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            sx={{ mb: 2 }}
          />

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              onClick={handleSaveApiKey}
              disabled={loading || !apiKey.trim()}
              sx={{
                bgcolor: '#e0e0e0',
                color: 'black',
                '&:hover': {
                  bgcolor: '#d0d0d0',
                }
              }}
            >
              {loading ? <CircularProgress size={24} /> : 'SAVE API KEY'}
            </Button>

            <Button
              variant="outlined"
              onClick={handleValidateApiKey}
              disabled={loading}
            >
              Validate API Key
            </Button>
          </Box>
        </Paper>
      )}

      {tabValue === 1 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Confluence Configuration
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Confluence URL"
                placeholder="https://your-domain.atlassian.net"
                value={confluenceUrl}
                onChange={(e) => setConfluenceUrl(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Username"
                placeholder="email@example.com"
                value={confluenceUsername}
                onChange={(e) => setConfluenceUsername(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                type="password"
                label="API Token"
                value={confluenceToken}
                onChange={(e) => setConfluenceToken(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleSaveConfluence}
                disabled={loading || !confluenceUrl.trim() || !confluenceUsername.trim() || !confluenceToken.trim()}
              >
                {loading ? <CircularProgress size={24} /> : 'Configure Confluence'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {status && (
        <Alert
          severity={status.startsWith('Error') ? 'error' : 'success'}
          sx={{ mt: 3 }}
          onClose={() => setStatus(null)}
        >
          {status}
        </Alert>
      )}
    </Box>
  );
};