import React, { useState } from "react";
import axios from "axios";
import MermaidRenderer from "./MermaidRenderer";
import "./App.css";

function App() {
  const [image, setImage] = useState(null);
  const [assetId, setAssetId] = useState("");
  const [diagramName, setDiagramName] = useState("");
  const [loading, setLoading] = useState(false);
  const [mermaidCode, setMermaidCode] = useState("");
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!image || !assetId || !diagramName) {
      alert("Please fill all fields.");
      return;
    }

    const formData = new FormData();
    formData.append("image", image);
    formData.append("asset_id", assetId);
    formData.append("diagram_name", diagramName);

    try {
      setLoading(true);
      const res = await axios.post("http://localhost:8001/upload/", formData);
      const { mermaid_code, summary, description } = res.data;
      const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;
      setMermaidCode(String(cleanCode));
      setSummary(summary);
      setDescription(description);
    } catch (err) {
      console.error("Upload failed:", err);
      alert("Upload failed. Check console.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <h1 className="app-title">🧠 Diagram Uploader & Visualizer</h1>
      <div className="main-content">
        {/* Left: Input Panel */}
        <div className="left-pane">
          <form className="upload-form" onSubmit={handleSubmit}>
            <label>
              Upload Image:
              <input type="file" accept="image/png, image/jpeg" onChange={(e) => setImage(e.target.files[0])} />
            </label>

            <label>
              Asset ID:
              <input type="text" value={assetId} onChange={(e) => setAssetId(e.target.value)} />
            </label>

            <label>
              Diagram Name:
              <input type="text" value={diagramName} onChange={(e) => setDiagramName(e.target.value)} />
            </label>

            <button type="submit" disabled={loading}>
              {loading ? "Processing..." : "Upload & Convert"}
            </button>
          </form>
        </div>

        {/* Right: Output Panel */}
        <div className="right-pane">
          {mermaidCode && (
            <div className="output-section">
              <h2>📈 Mermaid Diagram</h2>
              <MermaidRenderer chart={mermaidCode} />
            </div>
          )}

          {summary && (
            <div className="output-section">
              <h2>📝 Summary</h2>
              <h4>{diagramName}</h4>
              <p>{summary}</p>
            </div>
          )}

          {description && (
            <div className="output-section">
              <h2>📚 Description</h2>
              <p>{description}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
