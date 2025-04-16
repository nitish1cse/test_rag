import React, { useState, useEffect } from 'react';
import { Box, Button, Alert } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { serverService } from '../services/api';

export const ServerStatus: React.FC = () => {
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkServerStatus();
  }, []);

  const checkServerStatus = async () => {
    setLoading(true);
    const response = await serverService.checkStatus();
    setLoading(false);
    
    if (response.error) {
      setStatus('Offline');
    } else {
      setStatus('Online');
    }
  };

  return (
    <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
      <Alert 
        severity={status === 'Online' ? 'success' : 'error'}
        sx={{ flex: 1 }}
      >
        Server Status: {status || 'Checking...'}
      </Alert>
      <Button
        startIcon={<RefreshIcon />}
        onClick={checkServerStatus}
        disabled={loading}
        variant="outlined"
        size="small"
      >
        Refresh
      </Button>
    </Box>
  );
};