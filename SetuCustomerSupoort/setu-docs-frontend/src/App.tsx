import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Tabs,
  Tab,
  Box,
  CssBaseline,
  createTheme,
  ThemeProvider,
} from '@mui/material';
import { Chat } from './components/Chat';
import { ConfigurationPanel } from './components/ConfigurationPanel';
import { DocumentManager } from './components/DocumentManager';
import { ServerStatus } from './components/ServerStatus';
import { SlackManager } from './components/SlackManager';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
  },
});

const App: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1 }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Setu Documentation Assistant
            </Typography>
          </Toolbar>
          <Box sx={{ px: 2 }}>
            <Tabs
              value={tabValue}
              onChange={(_, newValue) => setTabValue(newValue)}
              textColor="inherit"
            >
              <Tab label="CHAT" />
              <Tab label="CONFIGURATION" />
              <Tab label="DOCUMENT CONFIGURATION" />
              <Tab label="SLACK INTEGRATION" />
            </Tabs>
          </Box>
        </AppBar>

        <ServerStatus />

        <Box>
          {tabValue === 0 && <Chat />}
          {tabValue === 1 && <ConfigurationPanel />}
          {tabValue === 2 && <DocumentManager />}
          {tabValue === 3 && <SlackManager />}
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;