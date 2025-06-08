import React, { useState } from 'react';
import { TextField, Button, Box, Paper } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
}

const QueryInput: React.FC<QueryInputProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(query);
  };

  return (
    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            multiline
            rows={4}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your Cypher query here..."
            variant="outlined"
            fullWidth
          />
          <Button
            type="submit"
            variant="contained"
            endIcon={<SendIcon />}
            disabled={isLoading || !query.trim()}
          >
            {isLoading ? 'Executing...' : 'Execute Query'}
          </Button>
        </Box>
      </form>
    </Paper>
  );
};

export default QueryInput;