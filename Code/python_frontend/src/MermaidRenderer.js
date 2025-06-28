import React, { useEffect, useRef } from "react";
import mermaid from "mermaid";

const MermaidRenderer = ({ chart }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!chart || typeof chart !== "string") {
      console.error("Invalid Mermaid chart provided:", chart);
      return;
    }

    mermaid.initialize({ startOnLoad: false });

    const renderDiagram = async () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = ""; // Clear previous diagram
        try {
          const { svg } = await mermaid.render(`generated-${Date.now()}`, chart);
          containerRef.current.innerHTML = svg;
        } catch (err) {
          console.error("Mermaid render failed:", err);
        }
      }
    };

    renderDiagram();
  }, [chart]);

  return <div ref={containerRef} />;
};

export default MermaidRenderer;
