import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import MermaidRenderer from "./MermaidRenderer";
import ReactMarkdown from "react-markdown";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { HiArrowUpCircle, HiMiniStopCircle } from "react-icons/hi2";

// import DiagramViewer from "./DiagramViewer";
import "./App.css";

cytoscape.use(fcose);

/** New: Diagram Viewer window opener logic using your existing MermaidRenderer and injected React */
function openDiagramViewer(diagramName, mermaidCode) {
    const diagramWindow = window.open("", "_blank", "width=800,height=600");
    if (!diagramWindow) return;

    //    const containerId = "mermaid-container-" + Date.now();

    diagramWindow.document.write(`
        <html>
            <head>
                <title>Diagram Viewer</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; background: #f4f6f8; }
                    h2 { color: #d9534f; margin-bottom: 20px; }
                    .download-btn { background: #d9534f; color: white; padding: 8px 12px; border: none; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                    .diagram-container { background: #fff; padding: 10px; border: 1px solid #ccc; border-radius: 6px; }
                </style>
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            </head>
            <body>
                <h2>Diagram: ${diagramName}</h2>
                <div class="diagram-container">
                    <pre class="mermaid">${mermaidCode}</pre>
                </div>
                <button class="download-btn" id="download-btn">Download AaC</button>
            </body>
        </html>
    `);

    diagramWindow.document.close();

    diagramWindow.onload = () => {
        if (diagramWindow.mermaid) {
            diagramWindow.mermaid.initialize({ startOnLoad: true });
        }

        const downloadBtn = diagramWindow.document.getElementById("download-btn");
        if (downloadBtn) {
            downloadBtn.onclick = () => {
                const blob = new Blob([mermaidCode], { type: "text/plain;charset=utf-8" });
                const url = URL.createObjectURL(blob);
                const link = diagramWindow.document.createElement("a");
                link.href = url;
                link.download = `${diagramName || "diagram"}.mmd`;
                link.click();
                URL.revokeObjectURL(url);
            };
        }
    };
}


export default function App() {
  const [activeTab, setActiveTab] = useState("upload");

  // Upload States
  const [image, setImage] = useState(null);
  const [assetId, setAssetId] = useState("");
  const [assetIdConf, setAssetIdConf] = useState("");
  const [diagramName, setDiagramName] = useState("");
  const [diagramNameConf, setDiagramNameConf] = useState("");
  const [loading, setLoading] = useState(false);
  const [mermaidCode, setMermaidCode] = useState("");
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [complexityTable, setComplexityTable] = useState([]);
  const [pros, setPros] = useState([]);
  const [cons, setCons] = useState([]);
  const [edges, setEdges] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [confluenceUrl, setConfluenceUrl] = useState("");
  /* View diagram const definitions*/
  const [archName, setArchName] = useState('');
  const [archSuggestions, setArchSuggestions] = useState([]);

  // Chat States
    const [sessionId, setSessionId] = useState("");
    const [query, setQuery] = useState("");
    const [chatHistory, setChatHistory] = useState([]);
  //  const [chatResponse, setChatResponse] = useState("");  Replaced by latestResponse
  //  const [latestResponse, setLatestResponse] = useState("");
    const [sending, setSending] = useState(false);
    // Detect Mermaid in latestResponse (for Chat)
  //  const containsMermaid = latestResponse?.includes("graph TD") || latestResponse?.includes("graph LR") || latestResponse?.includes("graph BT") || latestResponse?.includes("graph RL");
    // For auto scroll to end
    const messagesEndRef = useRef(null);
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatHistory]);


    // Domain and Capability states
    const [domain, setDomain] = useState('');
    const [capability, setCapability] = useState('');
    const [domainSuggestions, setDomainSuggestions] = useState([]);
    const [capabilitySuggestions, setCapabilitySuggestions] = useState([]);
    const [interfaceCounts, setInterfaceCounts] = useState([]);
    const [interfaceResults, setInterfaceResults] = useState([]);
    const cyRef = useRef();

    // App Connect Explorer States
    const [appIdInput, setAppIdInput] = useState("");
    const [appSuggestions, setAppSuggestions] = useState([]);
    const [direction, setDirection] = useState("Upstream");
    const [depth, setDepth] = useState(1);
    const [graphResults, setGraphResults] = useState([]);
    const cyGraphRef = useRef();

    const [activeSubTab, setActiveSubTab] = useState("import");

    // Streamed output for Agentic AI
    const [patternStreamResponses, setPatternStreamResponses] = useState([]);
    const [isPatternStreaming, setIsPatternStreaming] = useState(false);
    const agenticStreamEndRef = useRef(null);
    const [targetStreamResponses, setTargetStreamResponses] = useState([]);
    const [isTargetStreaming, setIsTargetStreaming] = useState(false);
    const [debugMode, setDebugMode] = useState(false);

    useEffect(() => {
      agenticStreamEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [patternStreamResponses, targetStreamResponses]);

  // Window title
  useEffect(() => {
        document.title = "ArchPilot";  // Set browser tab title
    }, []);

   // Use effect for Graph of Conn explorer
  useEffect(() => {
    if (graphResults.length > 0 && cyGraphRef.current) {
      const cy = cytoscape({
        container: cyGraphRef.current,
        elements: [],
        style: [
          {
              selector: 'node',
              style: {
                'background-color': '#d9534f',
                'label': 'data(label)',
                'color': '#fff',
                'text-valign': 'center',
                'text-halign': 'center',
                'font-size': '8px',
                'text-wrap': 'wrap',
                'text-max-width': 40,
                'width': 50,
                'height': 50,
                'border-width': 2,
                'border-color': '#000'
              }
            },
            {
              selector: 'edge',
              style: {
                'label': 'data(label)',
                'curve-style': 'bezier',
                'target-arrow-shape': 'triangle',
                'line-color': '#000',
                'target-arrow-color': '#000',
                'width': 2,
                'font-size': '8px',
                'text-background-color': '#fff',
                'text-background-opacity': 1,
                'text-background-padding': '2px'
                }
            }
        ],
        layout: { name: "fcose", animate: true },
      });

      const addedNodes = new Set();
      const addedEdges = new Set();

      graphResults.forEach((item) => {
        const source = item.n.id;
        const target = item.m.id;
        const relType = item.r[1];
        const sourceLabel = `${item.n.id}: ${item.n.name}`;
        const targetLabel = `${item.m.id}: ${item.m.name}`;
        const edgeId = `${source}-${target}-${relType}`;

        if (!addedNodes.has(source)) {
          cy.add({ data: { id: source, label: sourceLabel, trueId: item.n.id } });
          addedNodes.add(source);
        }
        if (!addedNodes.has(target)) {
          cy.add({ data: { id: target, label: targetLabel, trueId: item.m.id } });
          addedNodes.add(target);
        }
        if (!addedEdges.has(edgeId)) {
            cy.add({ data: { id: edgeId, source, target, sourceLabel, targetLabel, label: relType } });
            addedEdges.add(edgeId);
        }
      });

      cy.layout({ name: "fcose", animate: true }).run();

      cy.on('tap', 'node', async (event) => {
                const trueNodeId = event.target.data('trueId');
                if (!trueNodeId) return;

                try {
                    const res = await axios.get("http://localhost:7001/diagram_info", {
                        params: { node_id: trueNodeId }
                    });
                    if (res.data && res.data.mermaid_code && res.data.diagram_name) {
                        openDiagramViewer(res.data.diagram_name, res.data.mermaid_code);
                    } else {
                        alert('No diagram associated with this core asset.');
                    }
                } catch (err) {
                    console.error('Failed to fetch diagram info:', err);
                }
            });
    }
  }, [graphResults]);

  const fetchAppSuggestions = async (val) => {
    if (val.length >= 3) {
      try {
        const res = await axios.get("http://localhost:7001/search_assets", { params: { q: val } });
        setAppSuggestions(res.data.results || []);
      } catch (err) {
        console.error("Error fetching suggestions:", err);
      }
    } else {
      setAppSuggestions([]);
    }
  };

  const exploreConnections = async () => {
    if (!appIdInput) return alert("Please enter an App ID");
    try {
      const res = await axios.get("http://localhost:7001/query", {
        params: { node_id: appIdInput.trim(), type: direction, depth },
      });
      setGraphResults(res.data.results || []);
    } catch (err) {
      console.error("Failed to explore connections:", err);
      alert("Failed to explore connections");
    }
  };

   // Session ID global logic
   useEffect(() => {
        if (!sessionId) {
            axios.post("http://localhost:7001/generate_session/")
                .then(res => {
                    setSessionId(res.data.session_id);
                    console.log("Session initialized:", res.data.session_id);
                })
                .catch(err => console.error("Failed to generate session:", err));
        }
    }, [sessionId]);

    // Fetch domain suggestions
    const fetchDomainSuggestions = async (val) => {
        if (val.length >= 3) {
            try {
                const res = await axios.get('http://localhost:7001/get_domains', { params: { q: val } });
                setDomainSuggestions(res.data.results || []);
            } catch (err) {
                console.error('Error fetching domain suggestions:', err);
            }
        } else {
            setDomainSuggestions([]);
        }
    };

    // Fetch capability suggestions
    const fetchCapabilitySuggestions = async (val) => {
        if (val.length >= 3) {
            try {
                const res = await axios.get('http://localhost:7001/get_capabilities', { params: { q: val } });
                setCapabilitySuggestions(res.data.results || []);
            } catch (err) {
                console.error('Error fetching capability suggestions:', err);
            }
        } else {
            setCapabilitySuggestions([]);
        }
    };

    // Fetch interface type counts
    const fetchInterfaceCounts = async () => {
        try {
            if (!domain || !capability) {
                alert("Please enter both Domain and Capability.");
                return;
            }

            const res = await axios.get('http://localhost:7001/get_interface_type_counts', {
                params: { domain, capability }
            });

             if (Array.isArray(res.data) && res.data.length > 0) {
                setInterfaceCounts(res.data);
                setInterfaceResults([]);
             } else {
                setInterfaceCounts([]);
                setInterfaceResults([]);
                alert("No interfaces found for the given Domain and Capability.");
             }
        } catch (err) {
            console.error('Error fetching interface counts:', err);
            alert("Failed to fetch interface counts. Check if Domain and Capability exist.");
        }
    };

    // Fetch nodes by domain, capability, and interface type
    const fetchNodesByInterfaceType = async (type) => {
        try {
            const res = await axios.get('http://localhost:7001/get_nodes_by_d_c_interface', {
                params: { domain, capability, interface_type: type }
            });
            setInterfaceResults(res.data.results);
        } catch (err) {
            console.error('Error fetching nodes:', err);
        }
    };

  // View Diagram - Fetch architecture name suggestions
    const fetchArchSuggestions = async (val) => {
        if (val.length >= 3) {
            try {
                const res = await axios.get('http://localhost:7001/get_arch_names', { params: { q: val } });
                setArchSuggestions(res.data.results || []);
            } catch (err) {
                console.error('Error fetching architecture name suggestions:', err);
            }
        } else {
            setArchSuggestions([]);
        }
    };

  const handleImageChange = (event) => {
        setImage(event.target.files[0]);
    };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!image || !diagramName) {
      alert("Please fill all fields.");
      return;
    }

    const formData = new FormData();
    formData.append("image", image);
    formData.append("diagram_name", diagramName);
    formData.append("asset_id", assetId || "");

    try {
      setLoading(true);
      // Clear existing outputs before new upload
      setMermaidCode('');
      setSummary('');
      setDescription('');
      setPros([]);
      setCons([]);
      setEdges([]);
      setNodes([]);
      setComplexityTable([]);
      const res= await axios.post("http://localhost:7001/upload/", formData, {headers: { "Content-Type": "multipart/form-data" },});
      const { mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons } = res.data;
      const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;
      setMermaidCode(String(cleanCode));
      setSummary(summary);
      setDescription(description);
      setNodes(nodes || []);
      setEdges(edges || []);
      setComplexityTable(complexity_table || []);
      setPros(pros || []);
      setCons(cons || []);
      // Clear input fields after successful import
        setImage(null);
        setDiagramName('');
        setAssetId('');
    } catch (err) {
      console.error("Upload failed:", err);
      alert("Upload failed. Check console.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Confluence URL Import
  const handleConfluenceImport = async (e) => {
    e.preventDefault();

    if (!confluenceUrl || !diagramNameConf) {
        alert("Please fill all fields.");
        return;
    }

    const formData = new FormData();
    formData.append("confluence_url", confluenceUrl);
    formData.append("diagram_name", diagramNameConf);
    formData.append("asset_id", assetIdConf || "");

    try {
        setLoading(true);
        // Clear existing outputs before new import
        setMermaidCode('');
        setSummary('');
        setDescription('');
        setPros([]);
        setCons([]);
        setEdges([]);
        setNodes([]);
        setComplexityTable([]);

        const res = await axios.post("http://localhost:7001/process_confluence/", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });

        const { mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons } = res.data;

        const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;

        setMermaidCode(String(cleanCode));
        setSummary(summary);
        setDescription(description);
        setNodes(nodes || []);
        setEdges(edges || []);
        setComplexityTable(complexity_table || []);
        setPros(pros || []);
        setCons(cons || []);

        // Clear input fields after successful import
        setConfluenceUrl('');
        setDiagramNameConf('');
        setAssetIdConf('');

    } catch (err) {
        console.error("Confluence Import failed:", err);
        alert("Import failed. Check console.");
    } finally {
        setLoading(false);
    }
  };

  // View architecture - handler for button
  const handleViewDiagram = async (e) => {
    e.preventDefault();
    if (!archName) {
      alert("Please fill architecture name.");
      return;
    }

    try {
      // Clear all other states except mermaidCode
      setMermaidCode('');
      setSummary('');
      setDescription('');
      setPros([]);
      setCons([]);
      setEdges([]);
      setNodes([]);
      setComplexityTable([]);

      const res= await axios.get("http://localhost:7001/get_arch_code", { params: { arch_name: archName }});
      const { arch_name, mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons } = res.data;
      const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;
      setArchName(arch_name);
      setMermaidCode(String(cleanCode));
      setSummary(summary);
      setDescription(description);
      setNodes(nodes || []);
      setEdges(edges || []);
      setComplexityTable(complexity_table || []);
      setPros(pros || []);
      setCons(cons || []);
    } catch (err) {
      console.error("Architecture loading failed:", err);
      alert("Architecture loading failed. Check console.");
    }
  };

    const handleChatSubmit = async () => {
        if (!query || !sessionId) return;

        setSending(true);

        const formData = new FormData();
        formData.append("query", query);
        formData.append("session_id", sessionId);

        try {
            const res = await axios.post("http://localhost:7001/chat/", formData);
            const data = res.data;
            // setLatestResponse(data.response || "");
            const isMermaid = query?.includes("mermaid diagram") && (data.response?.includes("graph TD") || data.response?.includes("graph LR") || data.response?.includes("graph BT") || data.response?.includes("graph RL"));
                setChatHistory([
                  ...chatHistory,
                  { question: query, answer: data.response, isMermaid }
                ]);
            setQuery("");
        } catch (err) {
            console.error(err);
        } finally {
            setSending(false);
        }
    };

    /* Handle for Target Planner and Pattern Selector */

    const handleTargetPlanner = async () => {
          if (!archName) return;

          setTargetStreamResponses([]);
          setPatternStreamResponses([]);
          setIsTargetStreaming(true);

          try {
            const formData = new FormData();
            formData.append("arch_name", archName);

            const response = await fetch("http://localhost:7001/agent/target-planner/stream", {
              method: "POST",
              body: formData,
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            let buffer = "";

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });

              const events = buffer.split("\n\n");
              buffer = events.pop(); // hold incomplete part

              for (const event of events) {
                if (event.startsWith("data: ")) {
                  const jsonStr = event.replace("data: ", "").trim();

                  try {
                    const parsed = JSON.parse(jsonStr);

                    for (const stepKey in parsed) {
                      const stepData = parsed[stepKey];

                      // Handle thoughts (reasoning)
                      if (stepData.thoughts && debugMode) {
                        const thoughts = stepData.thoughts;
                        for (const thoughtKey in thoughts) {
                          const reasoning = thoughts[thoughtKey];
                          if (reasoning?.trim()) {
                            setTargetStreamResponses(prev => [
                              ...prev,
                              {
                                key: `Thinking: ${thoughtKey}`,
                                content: reasoning,
                                isThought: true,
                              },
                            ]);
                          }
                        }
                      }

                      // Handle main output
                      Object.entries(stepData).forEach(([key, value]) => {
                        if (key !== "thoughts") {
                          const content = typeof value === "object"
                            ? JSON.stringify(value, null, 2)
                            : value;

                          setTargetStreamResponses(prev => [
                            ...prev,
                            {
                              key,
                              content,
                              isThought: false,
                            },
                          ]);
                        }
                      });
                    }
                  } catch (err) {
                    console.error("Error parsing SSE:", err);
                  }
                }
              }
            }
          } catch (error) {
            console.error("Target Planner Error:", error);
          } finally {
            setIsTargetStreaming(false);
          }
        };

    const handlePatternSelector = async () => {
          if (!archName) return;

          setPatternStreamResponses([]);
          setTargetStreamResponses([]);
          setIsPatternStreaming(true);

          try {
            const formData = new FormData();
            formData.append("arch_name", archName);

            const response = await fetch("http://localhost:7001/agent/pattern-selector/stream", {
              method: "POST",
              body: formData,
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            let buffer = "";

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const events = buffer.split("\n\n");
              buffer = events.pop(); // Hold onto incomplete chunk

              for (const event of events) {
                if (!event.startsWith("data: ")) continue;

                const jsonStr = event.replace("data: ", "").trim();

                try {
                  const parsed = JSON.parse(jsonStr);

                  // Always take first key — supports extract, microservices, etc.
                  const [stepKey, stepValue] = Object.entries(parsed)[0];

                  if (stepValue && typeof stepValue === "object") {
                    const { info, summary, thoughts } = stepValue;

                    // Show thoughts (if debugMode is on)
                    if (debugMode && thoughts) {
                      for (const [thoughtKey, reasoning] of Object.entries(thoughts)) {
                        if (reasoning?.trim()) {
                          setPatternStreamResponses(prev => [
                            ...prev,
                            {
                              key: `Thinking: ${thoughtKey}`,
                              content: reasoning,
                              isThought: true,
                            },
                          ]);
                        }
                      }
                    }

                    // Show response (info or summary)
                    const content = info || summary || Object.values(stepValue).join("\n");
                    if (content?.trim()) {
                      setPatternStreamResponses(prev => [
                        ...prev,
                        {
                          key: stepKey,
                          content,
                        },
                      ]);
                    }
                  }

                } catch (err) {
                  console.error("Error parsing SSE event:", err, jsonStr);
                }
              }
            }

          } catch (error) {
            console.error("Pattern Selector Error:", error);
          } finally {
            setIsPatternStreaming(false);
          }
        };

    /* Handle Download AaC */
    const downloadMermaid = () => {
        const blob = new Blob([mermaidCode], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${diagramName || "diagram"}.mmd`;
        link.click();
        URL.revokeObjectURL(url);
    };

    /* Handle reset session */
    const handleResetSession = () => {
        if (!sessionId) return;

        const formData = new FormData();
        formData.append("session_id", sessionId);
        axios.post("http://localhost:7001/reset_session/", formData)
            .then(() => {
                setChatHistory([]);
                // setLatestResponse("");
                console.log("Session reset successful");

         // Generate new session
            axios.post("http://localhost:7001/generate_session/")
                .then(res => {
                    setSessionId(res.data.session_id);
                    console.log("New session started:", res.data.session_id);
                })
                .catch(err => console.error("Failed to generate new session:", err));
            })
            .catch(err => console.error("Reset failed:", err));
    };

    /* For domain_view */

    useEffect(() => {
        if (interfaceResults.length > 0 && cyRef.current) {
          const cy = cytoscape({
            container: cyRef.current,
            elements: [],
            style: [
              {
                selector: 'node',
                style: {
                    'background-color': '#d9534f',
                    'label': 'data(label)',
                    'color': '#fff',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '8px',
                    'text-wrap': 'wrap',
                    'text-max-width': 40,
                    'width': 50,
                    'height': 50,
                    'border-width': 2,
                    'border-color': '#000'
                  }
              },
              {
                selector: 'edge',
                style: {
                  'label': 'data(label)',
                  'curve-style': 'bezier',
                  'target-arrow-shape': 'triangle',
                  'line-color': '#000',
                  'target-arrow-color': '#000',
                  'width': 2,
                  'font-size': '8px',
                  'text-background-color': '#fff',
                  'text-background-opacity': 1,
                  'text-background-padding': '2px'
                }
              }
            ],
            layout: { name: 'fcose', animate: true }
          });

          const addedNodes = new Set();

          interfaceResults.forEach(row => {
            const source = row.from_node;
            const source_name = row.source_name;
            const target = row.to_node;
            const target_name = row.target_name;
            const sourceLabel = source_name ? `${source}: ${source_name}` : source;
            const targetLabel = target_name ? `${target}: ${target_name}` : target;

            if (!addedNodes.has(source)) {
              cy.add({ data: { id: source, label: sourceLabel } });
              addedNodes.add(source);
            }
            if (!addedNodes.has(target)) {
              cy.add({ data: { id: target, label: targetLabel } });
              addedNodes.add(target);
            }

            cy.add({ data: { id: `${source}-${target}-${row.interface_type}`, source, target, label: row.interface_type } });
          });

          cy.layout({ name: 'fcose', animate: true }).run();
        }
      }, [interfaceResults]);

  return (
        <div className="container">
            <h2 className="app-title">ArchPilot</h2>
            <div className="tab-container">
                {/* Tabs */}
                <div className="tabs">
                    <button className={`tab-button ${activeTab === "upload" ? "active" : ""}`} onClick={() => setActiveTab("upload")}>AaC Agent</button>
                    <button className={`tab-button ${activeTab === "explorer" ? "active" : ""}`} onClick={() => setActiveTab("explorer")}>DepScan Agent</button>
                    <button className={`tab-button ${activeTab === "chat" ? "active" : ""}`} onClick={() => setActiveTab("chat")}>ArchBOT</button>
                    <button className={`tab-button ${activeTab === "domain_view" ? "active" : ""}`} onClick={() => setActiveTab("domain_view")}>Arch Insights</button>
                    <button className={`tab-button ${activeTab === "agentic_ai" ? "active" : ""}`} onClick={() => setActiveTab("agentic_ai")}>Advanced Insights</button>
                </div>
            </div>
            <div className="tab-content">
            {/* Upload Tab */}
            {activeTab === "upload" && (
                <div className="flex-layout">
                    <div className="left-panel">
                        <h3>Generate Architectural Insights</h3>
                            <div className="subtabs">
                                <button
                                    className={`subtab-button ${activeSubTab === "confluence" ? "active" : ""}`}
                                    onClick={() => setActiveSubTab("confluence")}
                                >
                                    Confluence
                                </button>
                                <button
                                    className={`subtab-button ${activeSubTab === "import" ? "active" : ""}`}
                                    onClick={() => setActiveSubTab("import")}
                                >
                                    Import Architecture
                                </button>
                            </div>

                            {/* Subtab: Confluence */}
                            {activeSubTab === "confluence" && (
                                <div className="confluence-inputs">
                                    <input
                                        type="text"
                                        placeholder="Confluence Page URL"
                                        value={confluenceUrl}
                                        onChange={(e) => setConfluenceUrl(e.target.value)}
                                    /><br />
                                    <input
                                        type="text"
                                        placeholder="Core Asset ID (Optional)"
                                        value={assetIdConf}
                                        onChange={(e) => setAssetIdConf(e.target.value)}
                                    /><br />
                                    <input
                                        type="text"
                                        placeholder="Diagram Name"
                                        value={diagramNameConf}
                                        onChange={(e) => setDiagramNameConf(e.target.value)}
                                    /><br />
                                    <button className="primary-button" onClick={handleConfluenceImport} disabled={loading}>
                                         {loading ? "Importing..." : "Import"}
                                    </button>
                                    {/* Animation appears below button during loading */}
                                    {loading && (
                                    <div className="upload-animation">
                                        <div className="upload-step">⏳ Agent is building architecture knowledge base</div>
                                    </div>
                                    )}
                                </div>
                            )}

                            {/* Subtab: Import Architecture */}
                            {activeSubTab === "import" && (
                            <>
                                <input type="file" onChange={handleImageChange} /><br />
                                    <input
                                    type="text"
                                        placeholder="Core Asset ID (Optional)"
                                        value={assetId}
                                    onChange={(e) => setAssetId(e.target.value)}
                                    /><br />
                                    <input
                                    type="text"
                                        placeholder="Diagram Name"
                                        value={diagramName}
                                    onChange={(e) => setDiagramName(e.target.value)}
                                    /><br />
                                    <button className="primary-button" onClick={handleUpload} disabled={loading}>
                                        {loading ? "Importing..." : "Import"}
                                    </button>
                                    {/* Animation appears below button during loading */}
                                    {loading && (
                                    <div className="upload-animation">
                                        <div className="upload-step">⏳ Agent is building architecture knowledge base</div>
                                    </div>
                                    )}
                            </>
                        )}

                        {/* View Architecture - sub item in upload tab*/}
                        <hr />
                        <h3>View Architectural Insights</h3>
                            <label>Select architecture</label>
                            <div className="suggestion-wrapper">
                              <input type="text" className="input-box" value={archName} onChange={(e) => { setArchName(e.target.value); fetchArchSuggestions(e.target.value); }} placeholder="Enter Architecture Name" />
                              {archSuggestions.length > 0 && (
                                <ul className="suggestion-list">
                                  {archSuggestions.map((s, i) => <li key={i} onClick={() => { setArchName(s); setArchSuggestions([]); }}>{s}</li>)}
                                </ul>
                              )}
                            </div>
                            <button className="primary-button" onClick={handleViewDiagram}>Click to View</button>
                    </div>

                    <div className="right-panel">
                        {mermaidCode && (
                            <>
                                <h3>Mermaid Diagram</h3>
                                <MermaidRenderer chart={mermaidCode} />
                                <button className="download-btn" onClick={downloadMermaid}>
                                    Download AaC
                                </button>
                            </>
                        )}

                        {summary && (
                            <>
                                <h3>Summary</h3>
                                <p>{summary}</p>
                            </>
                        )}

                        {description && (
                            <>
                                <h3>Description</h3>
                                <p>{description}</p>
                            </>
                        )}

                        {complexityTable.length > 0 && (
                            <>
                                <h3>System Complexity Table</h3>
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Component</th>
                                            <th>Complexity</th>
                                            <th>Reason</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {complexityTable.map((entry, index) => (
                                            <tr key={index}>
                                                <td>{entry.component}</td>
                                                <td>{entry.complexity}</td>
                                                <td>{entry.reason}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </>
                        )}

                        {pros.length > 0 && (
                            <>
                                <h3>Pros</h3>
                                <ul>
                                    {pros.map((item, index) => (
                                        <li key={index}>{item}</li>
                                    ))}
                                </ul>
                            </>
                        )}

                        {cons.length > 0 && (
                            <>
                                <h3>Cons</h3>
                                <ul>
                                    {cons.map((item, index) => (
                                        <li key={index}>{item}</li>
                                    ))}
                                </ul>
                            </>
                        )}

                        {edges.length > 0 && (
                            <>
                                <h3>Integration Table</h3>
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Source</th>
                                            <th>Target</th>
                                            <th>Integration Type</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {edges.map((edge, index) => (
                                            <tr key={index}>
                                                <td>{edge.source}</td>
                                                <td>{edge.target}</td>
                                                <td>{edge.label}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </>
                        )}

                        {nodes.length > 0 && (
                            <>
                                <h3>Asset Table</h3>
                                <table>
                                    <thead>
                                        <tr>
                                            <th>App ID</th>
                                            <th>App Name</th>
                                            <th>Group</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {nodes.map((app, index) => (
                                            <tr key={index}>
                                                <td>{app.id}</td>
                                                <td>{app.name}</td>
                                                <td>{app.group}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Dependency Explorer */}
            {activeTab === "explorer" && (
                <div className="flex-layout">
                  <div className="left-panel">
                    <h2>Dependency Explorer</h2>
                    <div className="suggestion-wrapper">
                        <label>Enter Application Id:</label>
                      <input type="text" className="input-box" value={appIdInput} onChange={(e) => { setAppIdInput(e.target.value); fetchAppSuggestions(e.target.value); }} placeholder="Start typing App ID" />
                      {appSuggestions.length > 0 && (
                          <ul className="suggestion-list">
                            {appSuggestions.map((s, i) => (
                              <li key={i} onClick={() => { setAppIdInput(s.id); setAppSuggestions([]); }}>
                                {s.id} ({s.domain} - {s.capability})
                              </li>
                            ))}
                          </ul>
                        )}
                    </div>

                    <label>Select direction:</label>
                    <div className="direction-buttons">
                      {['Upstream', 'Downstream', 'Both'].map((dir) => (
                        <button key={dir} className={`count-button ${direction === dir ? "active" : ""}`} onClick={() => setDirection(dir)}>{dir}</button>
                      ))}
                    </div>

                    <div className="depth-control">
                        <label>Depth: {depth}</label>
                        <input type="range" min="1" max="5" value={depth} onChange={(e) => setDepth(Number(e.target.value))} />
                        <span>{depth}</span>
                    </div>

                    <button className="primary-button" onClick={exploreConnections}>Explore Connections</button>
                  </div>

                  <div className="right-panel">
                    {graphResults.length > 0 ? (
                      <div ref={cyGraphRef} style={{ height: 500, border: "1px solid #ccc", marginTop: 20 }} />
                    ) : (
                      <p>No graph to display. Enter details and click Explore.</p>
                    )}
                  </div>
                </div>
              )}

            {/* Chat Tab */}
            {activeTab === "chat" && (
                <div className="chat-section">
                    {/* Header with Session ID */}
                    <div className="chat-header">
                        <span className="session-id-label">Session ID: {sessionId}</span>
                        <button className="reset-session-btn" title="Reset" onClick={handleResetSession}>
                            ⟳
                        </button>
                    </div>

                    {/* Chat messages list */}
                    <div className="chat-messages-container">
                        {chatHistory.map((chat, index) => (
                            <React.Fragment key={index}>
                                <div className="chat-message user-message">
                                    <div className="message-content">{chat.question}</div>
                                </div>
                                <div className="chat-message system-message">
                                    <div className="message-content">
                                        {chat.isMermaid ? (
                                            <>
                                                <h4>Mermaid Diagram</h4>
                                                <MermaidRenderer chart={chat.answer} />
                                            </>
                                        ) : (
                                            <ReactMarkdown>
                                                {chat.answer
                                                    .replace(/\|(\s*):---.*\|/g, match => `${match}\n`)
                                                    .replace(/\|\s*\|/g, "|\n|")
                                                }
                                            </ReactMarkdown>
                                        )}
                                    </div>
                                </div>
                            </React.Fragment>
                        ))}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Chat input fixed at bottom */}
                    <div className="chat-input-container">
                        <textarea
                            placeholder="Ask your question..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                        <button className="icon-only-btn" onClick={handleChatSubmit} disabled={sending}>
                            {sending ? (
                                <HiMiniStopCircle className="blinking-icon" size={40} />
                            ) : (
                                <HiArrowUpCircle size={40} />
                            )}
                        </button>
                    </div>
                </div>
            )}

            {/* Domain and Capability View */}
            {activeTab === "domain_view" && (
                <div className="flex-layout">
                  <div className="left-panel">
                    <h2>Domain and Capability View</h2>

                    <label>Domain Name</label>
                    <div className="suggestion-wrapper">
                      <input type="text" className="input-box" value={domain} onChange={(e) => { setDomain(e.target.value); fetchDomainSuggestions(e.target.value); }} placeholder="Enter Domain Name" />
                      {domainSuggestions.length > 0 && (
                        <ul className="suggestion-list">
                          {domainSuggestions.map((s, i) => <li key={i} onClick={() => { setDomain(s); setDomainSuggestions([]); }}>{s}</li>)}
                        </ul>
                      )}
                    </div>

                    <label>Capability Name</label>
                    <div className="suggestion-wrapper">
                      <input type="text" className="input-box" value={capability} onChange={(e) => { setCapability(e.target.value); fetchCapabilitySuggestions(e.target.value); }} placeholder="Enter Capability Name" />
                      {capabilitySuggestions.length > 0 && (
                        <ul className="suggestion-list">
                          {capabilitySuggestions.map((s, i) => <li key={i} onClick={() => { setCapability(s); setCapabilitySuggestions([]); }}>{s}</li>)}
                        </ul>
                      )}
                    </div>

                    <button className="primary-button" onClick={fetchInterfaceCounts}>Explore Interfaces</button>

                    <div className="interface-buttons">
                      {interfaceCounts.map((item, idx) => {
                        const type = Object.keys(item)[0];
                        const count = item[type];
                        return (
                          <button key={idx} className="count-button" onClick={() => fetchNodesByInterfaceType(type)}>{type}: {count}</button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="right-panel">
                    {interfaceResults.length > 0 && (
                      <table className="styled-table">
                        <thead>
                          <tr>
                            <th>From Application</th>
                            <th>To Application</th>
                            <th>Interface Type</th>
                          </tr>
                        </thead>
                        <tbody>
                          {interfaceResults.map((row, idx) => (
                            <tr key={idx}>
                              <td>{row.source_name ? `${row.from_node}: ${row.source_name}` : row.from_node}</td>
                              <td>{row.target_name ? `${row.to_node}: ${row.target_name}` : row.to_node}</td>
                              <td>{row.interface_type}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {interfaceResults.length > 0 && (
                      <div ref={cyRef} style={{ height: 500, border: '1px solid #ccc', marginTop: 20 }} />
                    )}
                  </div>
                </div>
              )}

            {/* Agentic AI Tab */}
            {activeTab === "agentic_ai" && (
              <div className="flex-layout">
                  <div className="left-panel">
                    <h3>Advanced Use Cases</h3>

                    <label>Select Architecture</label>
                    <div className="suggestion-wrapper">
                      <input
                        type="text"
                        className="input-box"
                        value={archName}
                        onChange={(e) => {
                          setArchName(e.target.value);
                          fetchArchSuggestions(e.target.value);
                        }}
                        placeholder="Enter Architecture Name"
                      />
                      {archSuggestions.length > 0 && (
                        <ul className="suggestion-list">
                          {archSuggestions.map((s, i) => (
                            <li key={i} onClick={() => {
                              setArchName(s);
                              setArchSuggestions([]);
                            }}>{s}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div style={{ marginBottom: "15px" }}>
                      <label className="debug-toggle">
                          <input
                            type="checkbox"
                            checked={debugMode}
                            onChange={(e) => setDebugMode(e.target.checked)}
                          />
                          <span className="slider"></span>
                          <span className="label-text">Show Reasoning</span>
                        </label>
                    </div>

                    <button className="primary-button" onClick={handleTargetPlanner} style={{ marginRight: '20px' }}>Target Planner</button>
                    <button className="primary-button" onClick={handlePatternSelector}>Pattern Selector</button>
                  </div>

                  <div className="right-panel">
                        <div className="chat-messages-container">
                          {[...targetStreamResponses, ...patternStreamResponses].map((msg, idx) => (
                              <div
                                key={idx}
                                className={`chat-message ${msg.isThought ? "user-message" : "system-message"}`}
                                style={{ alignSelf: msg.isThought ? "flex-end" : "flex-start" }}
                              >
                                <div className="message-content">
                                  <h4 style={{ marginBottom: "6px", color: msg.isThought ? "#555" : "#d9534f" }}>
                                    {msg.key.replace(/_/g, ' ').toUpperCase()}
                                  </h4>
                                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                              </div>
                            ))}

                          {(isTargetStreaming || isPatternStreaming) && (
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                              <span className="blinking-icon">⏳</span>
                              <span>{isTargetStreaming ? "Running Target Planner..." : "Running Pattern Selector..."}</span>
                            </div>
                          )}
                          <div ref={agenticStreamEndRef} />
                        </div>

                        {!(isTargetStreaming || isPatternStreaming) &&
                            targetStreamResponses.length === 0 &&
                            patternStreamResponses.length === 0 && (
                              <p>No output yet. Run a selector to generate insights.</p>
                          )}
                    </div>
                </div>
            )}

              </div>
        </div>
    );
}