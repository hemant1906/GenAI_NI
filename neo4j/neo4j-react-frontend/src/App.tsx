import React, { useState } from 'react';
import { Container, Box, Alert } from '@mui/material';
import QueryInput from './components/QueryInput';
import GraphVisualization from './components/GraphVisualization';
import axios from 'axios';

interface GraphData {
  nodes: any[];
  relationships: any[];
}

function App() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], relationships: [] });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleQuerySubmit = async (query: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8000/api/query', {
        cypher: query
      });
      setGraphData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <h1>Neo4j Graph Visualizer</h1>
        <QueryInput onSubmit={handleQuerySubmit} isLoading={isLoading} />
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <GraphVisualization data={graphData} />
      </Box>
    </Container>
  );
}

export default App;