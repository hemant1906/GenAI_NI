import React, { useCallback, useRef, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Paper, Box, Typography } from '@mui/material';

interface Node {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

interface Relationship {
  id: string;
  type: string;
  start: string;
  end: string;
  properties: Record<string, any>;
}

interface GraphData {
  nodes: Node[];
  relationships: Relationship[];
}

interface GraphVisualizationProps {
  data: GraphData;
}

const ICONS: Record<string, string> = {
  Person: '👤',
  Movie: '🎬',
  // Add more label-icon mappings as needed
};

const GraphVisualization: React.FC<GraphVisualizationProps> = ({ data }) => {
  const [hoverNode, setHoverNode] = useState<any | null>(null);
  const [hoverLink, setHoverLink] = useState<any | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const graphData = useMemo(() => ({
    nodes: data.nodes.map(node => ({
      ...node,
      label: node.labels[0] || 'Node',
      icon: ICONS[node.labels[0]] || '🔵',
    })),
    links: data.relationships.map(rel => ({
      source: rel.start,
      target: rel.end,
      type: rel.type,
      ...rel,
    })),
  }), [data]);

  // Draw node with icon and label
  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.label || 'Node';
    const icon = node.icon || '🔵';
    const fontSize = 14 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Draw icon
    ctx.fillText(icon, node.x, node.y - fontSize);

    // Draw label
    ctx.fillStyle = '#222';
    ctx.fillText(label, node.x, node.y + fontSize * 0.5);
  }, []);

  // Draw relationship label
  const linkCanvasObject = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = link.type;
    if (!label) return;
    const fontSize = 10 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.fillStyle = '#888';
    const startX = link.source.x;
    const startY = link.source.y;
    const endX = link.target.x;
    const endY = link.target.y;
    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2;
    ctx.fillText(label, midX, midY);
  }, []);

  // Tooltip
  const renderTooltip = () => {
    if ((hoverNode || hoverLink) && mousePos) {
      return (
        <Box
          sx={{
            position: 'absolute',
            left: mousePos.x + 10, // offset for better visibility
            top: mousePos.y + 10,
            bgcolor: 'white',
            p: 1,
            border: '1px solid #ccc',
            zIndex: 10,
            pointerEvents: 'none',
            minWidth: 180,
            maxWidth: 300,
            boxShadow: 3,
            fontSize: 13,
          }}
        >
          {hoverNode && (
            <>
              <Typography variant="subtitle2">Node</Typography>
              <Typography variant="body2">ID: {hoverNode.id}</Typography>
              <Typography variant="body2">Label: {hoverNode.label}</Typography>
              <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                Properties: {JSON.stringify(hoverNode.properties)}
              </Typography>
            </>
          )}
          {hoverLink && (
            <>
              <Typography variant="subtitle2">Relationship</Typography>
              <Typography variant="body2">Type: {hoverLink.type}</Typography>
              <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                Properties: {JSON.stringify(hoverLink.properties)}
              </Typography>
            </>
          )}
        </Box>
      );
    }
    return null;
  };

  return (
    <Paper
      elevation={3}
      sx={{ height: '600px', width: '100%', position: 'relative', overflow: 'hidden' }}
      onMouseMove={e => {
        const rect = e.currentTarget.getBoundingClientRect();
        setMousePos({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top
        });
      }}
      onMouseLeave={() => {
        setMousePos(null);
        setHoverNode(null);
        setHoverLink(null);
      }}
    >
      <ForceGraph2D
        graphData={graphData}
        width={window.innerWidth * 0.9}
        height={600}
        nodeCanvasObject={nodeCanvasObject}
        linkCanvasObject={linkCanvasObject}
        nodeRelSize={8}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        onNodeHover={node => {
          setHoverNode(node);
          setHoverLink(null);
        }}
        onLinkHover={link => {
          setHoverLink(link);
          setHoverNode(null);
        }}
      />
      {renderTooltip()}
    </Paper>
  );
};

export default GraphVisualization;