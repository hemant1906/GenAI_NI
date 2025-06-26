import React, { useState } from "react";
import axios from "axios";

function App() {
  const [image, setImage] = useState(null);
  const [diagramName, setDiagramName] = useState("");
  const [assetId, setAssetId] = useState("");
  const [status, setStatus] = useState("");
  const [diagramCode, setDiagramCode] = useState("");

  const handleUpload = async () => {
    if (!image || !assetId || !diagramName) {
      alert("Image, Diagram Name and Asset ID are required");
      return;
    }

    const formData = new FormData();
    formData.append("image", image);
    formData.append("diagram_name", diagramName);
    formData.append("asset_id", assetId);

    try {
      setStatus("Uploading image and generating Mermaid diagram...");
      const res = await axios.post("http://localhost:8000/upload/", formData);
      setDiagramCode(res.data.mermaid_code);
      setStatus("Diagram generated and saved successfully.");
    } catch (err) {
      console.error(err);
      setStatus("Failed to upload or process.");
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Upload Image for Mermaid Conversion</h2>

      <input
        type="file"
        accept="image/png,image/jpeg"
        onChange={e => setImage(e.target.files[0])}
      /><br /><br />

      <input
        type="text"
        placeholder="Enter Diagram Name"
        value={diagramName}
        onChange={e => setDiagramName(e.target.value)}
      /><br /><br />

      <input
        type="text"
        placeholder="Enter Asset ID"
        value={assetId}
        onChange={e => setAssetId(e.target.value)}
      /><br /><br />

      <button onClick={handleUpload}>Upload & Convert</button>
      <br /><br />

      <p>Status: {status}</p>
      {diagramCode && (
        <div>
          <h3>Generated Mermaid Code:</h3>
          <pre>{diagramCode}</pre>
        </div>
      )}
    </div>
  );
}

export default App;