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
  IconButton,
  FormControlLabel,
  Checkbox,
  Tooltip,
  Stack,
  Divider,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  AlertTitle,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { productService, slackService } from '../services/api';

export const SlackManager: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [products, setProducts] = useState<string[]>([]);
  const [channels, setChannels] = useState<Array<any>>([]);
  const [logs, setLogs] = useState<string[]>([]);

  // Slack API configuration
  const [apiToken, setApiToken] = useState('');
  const [botToken, setBotToken] = useState('');

  // Channel configuration
  const [channelId, setChannelId] = useState('');
  const [product, setProduct] = useState('');
  const [includeThreads, setIncludeThreads] = useState(true);
  const [maxMessages, setMaxMessages] = useState(1000);
  const [description, setDescription] = useState('');

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [channelToDelete, setChannelToDelete] = useState<string | null>(null);

  // Add these state variables at the top with other states
  const [rateLimits, setRateLimits] = useState<any>(null);
  const [batchSize, setBatchSize] = useState(50);
  const [batchDelay, setBatchDelay] = useState(30);
  const [channelDelay, setChannelDelay] = useState(5);
  const [failureDelay, setFailureDelay] = useState(10);

  useEffect(() => {
    loadProducts();
    loadChannels();
    loadRateLimits();
  }, []);

  const loadProducts = async () => {
    setLoading(true);
    const response = await productService.getProducts();
    setLoading(false);

    if (response.data) {
      setProducts(response.data);
    } else {
      console.error('Error loading products:', response.error);
    }
  };

  const loadChannels = async () => {
    setLoading(true);
    const response = await slackService.listChannels();
    setLoading(false);

    if (response.data) {
      setChannels(response.data.channels || []);
    } else {
      console.error('Error loading channels:', response.error);
    }
  };

  const loadLogs = async () => {
    setLoading(true);
    const response = await slackService.getLogs(500); // Get last 500 lines
    setLoading(false);

    if (response.data) {
      setLogs(response.data.logs || []);
    } else {
      console.error('Error loading logs:', response.error);
      setStatus(`Error loading logs: ${response.error}`);
    }
  };

  const loadRateLimits = async () => {
    const response = await slackService.getRateLimits();
    
    if (response.data && response.data.settings) {
      setRateLimits(response.data.settings);
      setBatchSize(response.data.settings.batch_size || 5);
      setBatchDelay(response.data.settings.batch_delay || 30);
      setChannelDelay(response.data.settings.channel_delay || 5);
      setFailureDelay(response.data.settings.failure_delay || 10);
    } else {
      console.error('Error loading rate limits:', response.error);
    }
  };

  const handleConfigureSlack = async () => {
    if (!apiToken) return;

    setLoading(true);
    const response = await slackService.configureApi(
      apiToken,
      botToken || undefined
    );
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Slack API configured successfully');
      setApiToken('');
      setBotToken('');
    }
  };

  const handleConfigureChannel = async () => {
    if (!channelId || !product) return;

    setLoading(true);
    const response = await slackService.configureChannel(
      channelId,
      product,
      includeThreads,
      maxMessages,
      description || undefined
    );
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Channel configured successfully');
      setChannelId('');
      setDescription('');
      loadChannels();
    }
  };

  const handleDeleteChannel = async (channelId: string) => {
    setChannelToDelete(channelId);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteChannel = async () => {
    if (!channelToDelete) return;
    
    setLoading(true);
    const response = await slackService.deleteChannel(channelToDelete);
    setLoading(false);
    setDeleteDialogOpen(false);
    setChannelToDelete(null);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Channel deleted successfully');
      loadChannels();
    }
  };

  const cancelDeleteChannel = () => {
    setDeleteDialogOpen(false);
    setChannelToDelete(null);
  };

  const handleProcessChannel = async (channelId: string) => {
    setProcessing(channelId);
    
    try {
      const response = await slackService.processChannel(channelId);
      
      if (response.error) {
        setStatus(`Error: ${response.error}`);
      } else {
        setStatus(response.data?.message || 'Channel processed successfully');
        loadChannels();
      }
    } catch (error) {
      console.error("Error processing channel:", error);
      setStatus(`Error processing channel: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setProcessing(null);
    }
  };

  const handleProcessAllChannels = async () => {
    setProcessing('all');
    
    try {
      const response = await slackService.processAllChannels();
      
      if (response.error) {
        setStatus(`Error: ${response.error}`);
      } else {
        setStatus(response.data?.message || 'All channels processed successfully');
        loadChannels();
      }
    } catch (error) {
      console.error("Error processing all channels:", error);
      setStatus(`Error processing all channels: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setProcessing(null);
    }
  };

  const handleConfigureRateLimits = async () => {
    setLoading(true);
    const response = await slackService.configureRateLimits(
      batchSize,
      batchDelay,
      channelDelay,
      failureDelay
    );
    setLoading(false);

    if (response.error) {
      setStatus(`Error: ${response.error}`);
    } else {
      setStatus(response.data?.message || 'Rate limits configured successfully');
      loadRateLimits();
    }
  };

  useEffect(() => {
    if (tabValue === 3) {
      loadLogs();
    }
  }, [tabValue]);

  // Add this function to calculate estimated processing time
  const getEstimatedProcessingTime = (channel: any): string => {
    if (!rateLimits || !channel) return "Unknown";
    
    // Estimate based on messages and rate limits
    const messagesPerHour = 600; // Rough estimate
    const lastProcessed = channel.last_processed ? 
      new Date(parseFloat(channel.last_processed) * 1000) : null;
    
    // If never processed, use rough estimate
    if (!lastProcessed) {
      return "5-10 minutes (first run)";
    }
    
    // Calculate days since last processed
    const daysSinceProcessed = (new Date().getTime() - lastProcessed.getTime()) / (1000 * 60 * 60 * 24);
    
    // Rough message count estimate based on channel activity
    const estimatedMessages = Math.min(1000, Math.round(daysSinceProcessed * 100));
    const estimatedMinutes = Math.max(1, Math.round(estimatedMessages / messagesPerHour * 60));
    
    if (estimatedMinutes < 5) {
      return "< 5 minutes";
    } else if (estimatedMinutes < 60) {
      return `~${estimatedMinutes} minutes`;
    } else {
      return `~${Math.round(estimatedMinutes / 60)} hours`;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="Slack API Configuration" />
        <Tab label="Channel Configuration" />
        <Tab label="Manage Channels" />
        <Tab label="Performance Settings" />
        <Tab label="Processing Logs" />
      </Tabs>

      {tabValue === 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Configure Slack API Credentials
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Slack API Token"
                placeholder="xoxp-..."
                type="password"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                helperText="The Slack API token with scopes: channels:history, channels:read, users:read"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Slack Bot Token (Optional)"
                placeholder="xoxb-..."
                type="password"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                helperText="Optional bot token if needed"
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleConfigureSlack}
                disabled={loading || !apiToken}
              >
                {loading ? <CircularProgress size={24} /> : 'Configure Slack API'}
              </Button>
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 3 }} />
              <Typography variant="h6" gutterBottom>
                Processing Settings
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Configure rate limits and processing parameters to optimize performance.
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label="Batch Size"
                value={batchSize}
                onChange={(e) => setBatchSize(parseInt(e.target.value))}
                helperText="Number of channels to process in one batch"
                inputProps={{ min: 1, max: 20 }}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label="Batch Delay (seconds)"
                value={batchDelay}
                onChange={(e) => setBatchDelay(parseInt(e.target.value))}
                helperText="Seconds to wait between processing batches"
                inputProps={{ min: 5, max: 120 }}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label="Channel Delay (seconds)"
                value={channelDelay}
                onChange={(e) => setChannelDelay(parseInt(e.target.value))}
                helperText="Seconds to wait between processing channels"
                inputProps={{ min: 1, max: 30 }}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label="Failure Delay (seconds)"
                value={failureDelay}
                onChange={(e) => setFailureDelay(parseInt(e.target.value))}
                helperText="Seconds to wait after a failure"
                inputProps={{ min: 1, max: 60 }}
              />
            </Grid>
            
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleConfigureRateLimits}
                disabled={loading}
                sx={{ mt: 1 }}
              >
                {loading ? <CircularProgress size={24} /> : 'Update Processing Settings'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {tabValue === 1 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Configure a Slack Channel
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Slack Channel ID"
                placeholder="C012AB3CD"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                helperText="The ID of the Slack channel to monitor"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                label="Select Product"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                helperText="The product to associate with messages from this channel"
              >
                {products.map((product) => (
                  <MenuItem key={product} value={product}>{product}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description (Optional)"
                placeholder="Customer support channel for payments"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                helperText="A description of this channel's purpose"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={includeThreads}
                    onChange={(e) => setIncludeThreads(e.target.checked)}
                  />
                }
                label="Include threads"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label="Max Messages"
                value={maxMessages}
                onChange={(e) => setMaxMessages(parseInt(e.target.value))}
                inputProps={{ min: 10, max: 10000 }}
                helperText="Maximum messages to retrieve per channel"
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleConfigureChannel}
                disabled={loading || !channelId || !product}
              >
                {loading ? <CircularProgress size={24} /> : 'Configure Channel'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {tabValue === 2 && (
        <Paper sx={{ p: 3 }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
            <Typography variant="h6">
              Configured Slack Channels
            </Typography>
            <IconButton color="primary" onClick={loadChannels} title="Refresh channels">
              <RefreshIcon />
            </IconButton>
            <Box sx={{ flexGrow: 1 }} />
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={handleProcessAllChannels}
              disabled={loading || channels.length === 0 || processing !== null}
            >
              {processing === 'all' ? <CircularProgress size={24} /> : 'Process All Channels'}
            </Button>
          </Stack>

          {channels.length === 0 ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              No Slack channels configured yet. Add a channel in the Channel Configuration tab.
            </Alert>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Channel Name</TableCell>
                    <TableCell>Channel ID</TableCell>
                    <TableCell>Product</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Last Processed</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {channels.map((channel) => (
                    <TableRow key={channel.channel_id}>
                      <TableCell>{channel.channel_name}</TableCell>
                      <TableCell>{channel.channel_id}</TableCell>
                      <TableCell>{channel.product}</TableCell>
                      <TableCell>{channel.description}</TableCell>
                      <TableCell>
                        {channel.last_processed 
                          ? new Date(parseFloat(channel.last_processed) * 1000).toLocaleString() 
                          : 'Never'}
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={1}>
                          <Tooltip title="Process channel">
                            <IconButton 
                              color="primary"
                              onClick={() => handleProcessChannel(channel.channel_id)}
                              disabled={processing !== null}
                            >
                              {processing === channel.channel_id ? (
                                <CircularProgress size={24} />
                              ) : (
                                <PlayArrowIcon />
                              )}
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete channel">
                            <IconButton 
                              color="error"
                              onClick={() => handleDeleteChannel(channel.channel_id)}
                              disabled={loading}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      )}

      {tabValue === 3 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Performance Settings
          </Typography>
          
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="subtitle1" gutterBottom>
                  Document Processing Configuration
                </Typography>
                
                <Box sx={{ mt: 2 }}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Batch Size"
                    value={batchSize}
                    onChange={(e) => setBatchSize(parseInt(e.target.value))}
                    helperText="Number of documents to process in one batch"
                    sx={{ mb: 2 }}
                    inputProps={{ min: 10, max: 100 }}
                  />
                  
                  <Alert severity="info" sx={{ mt: 2 }}>
                    For best performance, batch documents into groups of 50-100. 
                    Larger batches process faster but use more memory.
                  </Alert>
                  
                  <Button
                    variant="contained"
                    onClick={handleConfigureRateLimits}
                    disabled={loading}
                    sx={{ mt: 3 }}
                  >
                    Update Settings
                  </Button>
                </Box>
              </Paper>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="subtitle1" gutterBottom>
                  Processing Estimates
                </Typography>
                
                {channels.length > 0 ? (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Channel</TableCell>
                          <TableCell>Est. Processing Time</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {channels.map((channel) => (
                          <TableRow key={channel.channel_id}>
                            <TableCell>{channel.channel_name}</TableCell>
                            <TableCell>{getEstimatedProcessingTime(channel)}</TableCell>
                          </TableRow>
                        ))}
                        <TableRow>
                          <TableCell><strong>All Channels</strong></TableCell>
                          <TableCell>
                            <strong>
                              {channels.length > 0 
                                ? `~${Math.max(10, Math.round(channels.length * 5))} minutes`
                                : "N/A"}
                            </strong>
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </TableContainer>
                ) : (
                  <Alert severity="info">
                    No channels configured. Add channels to see processing estimates.
                  </Alert>
                )}
              </Paper>
            </Grid>
            
            <Grid item xs={12}>
              <Alert severity="warning">
                <AlertTitle>Performance Tips</AlertTitle>
                <ul>
                  <li>Processing is slower the first time a channel is processed.</li>
                  <li>Large channels with many messages can take 10-30 minutes to process.</li>
                  <li>Subsequent processing runs only fetch new messages and are much faster.</li>
                  <li>For best performance, process channels during off-peak hours.</li>
                </ul>
              </Alert>
            </Grid>
          </Grid>
        </Paper>
      )}

      {tabValue === 4 && (
        <Paper sx={{ p: 3 }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
            <Typography variant="h6">
              Slack Processing Logs
            </Typography>
            <IconButton color="primary" onClick={loadLogs} title="Refresh logs">
              <RefreshIcon />
            </IconButton>
          </Stack>

          <Box sx={{ 
            bgcolor: 'background.paper', 
            border: '1px solid #ddd', 
            borderRadius: 1, 
            p: 2, 
            height: '500px', 
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '0.85rem',
            whiteSpace: 'pre-wrap'
          }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <CircularProgress />
              </Box>
            ) : logs.length === 0 ? (
              <Typography color="text.secondary">No logs found. Process a channel to generate logs.</Typography>
            ) : (
              logs.map((log, index) => (
                <Box key={index} sx={{ 
                  py: 0.5,
                  borderBottom: '1px solid #f0f0f0',
                  color: log.includes('ERROR') ? 'error.main' : 
                         log.includes('WARNING') ? 'warning.main' : 
                         'text.primary'
                }}>
                  {log}
                </Box>
              ))
            )}
          </Box>
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

      <Dialog
        open={deleteDialogOpen}
        onClose={cancelDeleteChannel}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          Delete Channel Configuration
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            Are you sure you want to delete this channel configuration? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelDeleteChannel}>Cancel</Button>
          <Button onClick={confirmDeleteChannel} color="error" autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}; 