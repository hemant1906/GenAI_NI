// MermaidRenderer.js

import React, { useEffect, useRef } from "react";
import mermaid from "mermaid";

const MermaidRenderer = ({ chart }) => {
  const containerRef = useRef(null);
  const id = useRef(`mermaid-diagram-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`);

  useEffect(() => {
    if (!chart || typeof chart !== "string") {
      console.error("MermaidRenderer: Invalid chart", chart);
      return;
    }

    mermaid.initialize({ startOnLoad: false });

    const el = document.getElementById(id.current);
    if (el) {
      try {
        // Direct init from <pre><code> block
        mermaid.init(undefined, el);
      } catch (err) {
        console.error("Mermaid init failed:", err);
      }
    }
  }, [chart]);

  return (
    <div ref={containerRef}>
      <pre className="mermaid" id={id.current}>
        {chart}
      </pre>
    </div>
  );
};

export default MermaidRenderer;
