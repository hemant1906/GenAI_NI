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

function sanitizeMermaidClassDiagram(raw) {
  // First, aggressively replace non-breaking spaces with standard spaces
  // This is crucial if the model is consistently outputting them
  let cleaned = raw.replace(/\u00A0/g, ' '); // Replace non-breaking space (U+00A0) with standard space (U+0020)

  // Now apply other sanitization steps
  cleaned = cleaned
    // Removes quotes around relationship labels (e.g., : "label" -> : label)
    // and ensures there's only one space after colon
    .replace(/: *"?([a-zA-Z0-9_]+)"?/g, ': $1')
    // This regex looks problematic for class diagrams, it seems more for ERD relationships
    // and might incorrectly reformat attributes or methods.
    // If you're trying to fix multi-space indentation, a different approach is needed.
    // .replace(/\n\s+([a-zA-Z0-9_]+) *:([a-zA-Z0-9_]+)/g, '\n$1 : $2')
    // If you're trying to normalize indentation:
    .replace(/^( *)(\S.*)/gm, (match, p1, p2) => {
        // This is a more robust way to normalize leading whitespace to 4 spaces
        // Adjust the '4' if your diagram uses a different standard indent
        const indentLevel = Math.floor(p1.length / 4);
        return '    '.repeat(indentLevel) + p2;
    })
    // Removes quotes around cardinalities (e.g., "1..*" -> 1..*)
    .replace(/"(\d|\*|\d\.\.\d)"/g, '$1')
    // Removes visibility modifiers (+ or -) at the start of a line, globally and multi-line
    .replace(/^\s*[+-]/gm, '')
    // Aggressive removal of any remaining non-ASCII characters if not caught by \u00A0 replacement
    .replace(/[^\u0020-\u007E\n]/g, ''); // Ensure newline is not removed

    return cleaned;
}

function sanitizeMermaidERDiagram(raw) {
  // CRITICAL: First, aggressively replace non-breaking spaces with standard spaces.
  // This addresses the primary issue identified in your previous outputs (\u00A0).
  let cleaned = raw.replace(/\u00A0/g, ' ');

  // General whitespace normalization: replace multiple spaces with a single space,
  // but be careful not to collapse essential indentation or newline structures.
  // This is a broader fix if other inconsistent whitespace appears.
  // cleaned = cleaned.replace(/ {2,}/g, ' '); // Use with caution, can break specific indentation

  // More robust indentation normalization: ensure consistent leading spaces
  // This will convert any leading sequence of spaces (or potentially tabs if present)
  // to consistent 4-space indents. Adjust '4' if your target standard is different.
  cleaned = cleaned.replace(/^( *)(\S.*)/gm, (match, p1, p2) => {
      // Calculate effective indent level based on original leading whitespace
      const indentLevel = Math.floor(p1.length / 4);
      return '    '.repeat(indentLevel) + p2;
  });

  // Remove any remaining non-ASCII characters that are not standard spaces or newlines.
  // This acts as a final catch-all for other problematic invisible characters.
  cleaned = cleaned.replace(/[^\u0020-\u007E\n]/g, ''); // Preserve standard ASCII range and newlines

  // --- ERD-specific sanitization ---

  // 1. Ensure relationship labels do NOT have quotes (e.g., : "owns" -> : owns)
  //    and handle potential extra spaces around the colon and label.
  //    Also ensures camelCase/PascalCase labels are not split by accidental spaces.
  cleaned = cleaned.replace(/: *"?([a-zA-Z][a-zA-Z0-9_]*)"?/g, ': $1');

  // 2. Remove quotes around cardinalities if they appear (e.g., "||--o{" -> ||--o{)
  //    Mermaid ERD cardinalities generally should not be quoted.
  //    This regex targets common Mermaid cardinality patterns.
  cleaned = cleaned.replace(/"(\|\|--\|\||\|\|--o\}|\}o--\|\||\}o--o\{)"/g, '$1');

  // 3. Remove any leading/trailing visibility modifiers (+/-) which are not used in ERD
  //    This is more common in Class Diagrams but good to include as a safeguard.
  cleaned = cleaned.replace(/^\s*[+-]\s*/gm, '');

  // 4. Ensure attribute types are simple (int, string) and not complex types or arrays.
  //    The prompt specified 'string' or 'int'. This regex removes anything beyond.
  //    NOTE: This is a complex one and might need fine-tuning based on *actual* bad output
  //    If the model sometimes adds things like 'string[]' or 'json', this can help.
  //    Example: `attributeName string[].`  -> `attributeName.`
  //    It targets attribute lines with a known type.
  cleaned = cleaned.replace(/^( *[a-zA-Z0-9_]+) (int|string)\s*(\S.*)?$/gm, '$1 $2$3'); // Keeps type but removes extra spaces if any

  return cleaned;
}

/* TO DELETE
// In your frontend JavaScript:
const rawMermaidOutput = "**Class Diagram (Mermaid)**\n```classDiagram\n    class PrivateBankingClientPortal {\n        clientId\n        sessionToken\n        viewPortfolio()\n        executeTrade()\n    }\n    class MobileBankingApp {\n        deviceId\n        pushToken\n        checkBalance()\n        transferFunds()\n    }\n    class OnlineBankingPortal {\n        userId\n        lastLogin\n        payBill()\n        viewStatements()\n    }\n    class EnterpriseEventingPlatform {\n        topicName\n        eventPayload\n        publishEvent()\n        subscribeToTopic()\n    }\n    class APIGateway {\n        apiKey\n        requestPath\n        routeRequest()\n        authenticate()\n    }\n    class RealtimeDataIntegrationService {\n        sourceSystem\n        targetSystem\n        streamData()\n        transformRecord()\n    }\n    class PartyLifecycleManagementSystem {\n        partyId\n        partyStatus\n        createParty()\n        updatePartyDetails()\n    }\n    class DigitalOnboardingPlatformBusiness {\n        applicationId\n        onboardingStatus\n        initiateOnboarding()\n        verifyDocuments()\n    }\n    class CustomerOnboardingSystemRetail {\n        customerId\n        applicationData\n        processRetailApplication()\n        approveCustomer()\n    }\n    class IdentityProofingServiceExternal {\n        verificationId\n        result\n        verifyIdentity()\n        checkSanctionsList()\n    }\n    class KYCCDDPlatform {\n        caseId\n        riskScore\n        performKYC()\n        runCDD()\n    }\n    class CustomerDataPrivacyManagement {\n        consentId\n        dataSubjectId\n        manageConsent()\n        anonymizeData()\n    }\n    class GlobalCustomerIDRegistry {\n        globalCustomerId\n        masterRecord\n        resolveCustomerId()\n        mergeDuplicates()\n    }\n    class CRMBusinessPrivateBanking {\n        clientId\n        relationshipManager\n        logInteraction()\n        viewClient360()\n    }\n    class CRMRetailPersonalBanking {\n        customerId\n        customerSegment\n        updateCustomerProfile()\n        trackCampaignResponse()\n    }\n    class DigitalCustomerEngagementPlatform {\n        campaignId\n        targetAudience\n        sendNotification()\n        trackEngagement()\n    }\n    class AutomatedCustomerOutreachPlatform {\n        outreachId\n        channel\n        triggerCommunication()\n        trackResponse()\n    }\n    class AIDrivenCustomerServiceBot {\n        conversationId\n        intent\n        answerQuery()\n        escalateToAgent()\n    }\n    class ChatbotforCorporateSupport {\n        ticketId\n        corporateClientId\n        provideSupport()\n        logIssue()\n    }\n\n    PrivateBankingClientPortal --> APIGateway : usesAPI\n    MobileBankingApp --> APIGateway : usesAPI\n    OnlineBankingPortal --> APIGateway : usesAPI\n    APIGateway --> DigitalOnboardingPlatformBusiness : routesTo\n    APIGateway --> CustomerOnboardingSystemRetail : routesTo\n    APIGateway --> AutomatedCustomerOutreachPlatform : triggers\n    EnterpriseEventingPlatform --> RealtimeDataIntegrationService : pushesEvent\n    RealtimeDataIntegrationService --> PartyLifecycleManagementSystem : streamsData\n    DigitalOnboardingPlatformBusiness --> PartyLifecycleManagementSystem : publishesEvent\n    DigitalOnboardingPlatformBusiness --> IdentityProofingServiceExternal : callsAPI\n    CustomerOnboardingSystemRetail --> PartyLifecycleManagementSystem : publishesEvent\n    CustomerOnboardingSystemRetail --> IdentityProofingServiceExternal : callsAPI\n    PartyLifecycleManagementSystem --> GlobalCustomerIDRegistry : syncsViaEvent\n    PartyLifecycleManagementSystem --> CRMBusinessPrivateBanking : updatesViaAPI\n    PartyLifecycleManagementSystem --> CRMRetailPersonalBanking : syncsViaEvent\n    PartyLifecycleManagementSystem --> KYCCDDPlatform : triggersViaEvent\n    GlobalCustomerIDRegistry --> CRMBusinessPrivateBanking : providesData\n    KYCCDDPlatform --> CustomerDataPrivacyManagement : callsAPI\n    CRMBusinessPrivateBanking --> DigitalCustomerEngagementPlatform : feedsData\n    CRMRetailPersonalBanking --> DigitalCustomerEngagementPlatform : feedsData\n    DigitalCustomerEngagementPlatform --> AIDrivenCustomerServiceBot : powers\n    DigitalCustomerEngagementPlatform --> ChatbotforCorporateSupport : powers\n```\n\n"; // Get this from your backend response
const rawDataModelOutput = "**Data Model (Mermaid ERD)**\n```erDiagram\n    Customer {\n        int CustomerID PK\n        string GlobalID\n        string CustomerType\n        string Status\n        string CreatedAt\n        string UpdatedAt\n    }\n    Account {\n        int AccountID PK\n        int CustomerID FK\n        string AccountNumber\n        string AccountType\n        string Balance\n        string Status\n    }\n    OnboardingApplication {\n        int ApplicationID PK\n        string Channel\n        string Status\n        string SubmittedAt\n        string ApprovedAt\n        string CreatedBy\n    }\n    IdentityVerification {\n        int VerificationID PK\n        int ApplicationID FK\n        string Provider\n        string Result\n        string CheckedAt\n        string TransactionID\n    }\n    UserSession {\n        int SessionID PK\n        int CustomerID FK\n        string Channel\n        string DeviceInfo\n        string StartTime\n        string EndTime\n    }\n    Consent {\n        int ConsentID PK\n        int CustomerID FK\n        string ConsentType\n        string Status\n        string GrantedAt\n        string ExpiresAt\n    }\n    CustomerSegment {\n        int SegmentID PK\n        string SegmentName\n        string Criteria\n        string CreatedAt\n    }\n    ApiLog {\n        int LogID PK\n        string RequestID\n        string Endpoint\n        string SourceSystem\n        string Timestamp\n        int StatusCode\n    }\n    EventLog {\n        int EventID PK\n        string EventType\n        string Topic\n        string Producer\n        string Timestamp\n        string Payload\n    }\n    AuditLog {\n        int AuditID PK\n        string EntityName\n        string EntityID\n        string Action\n        string ChangedBy\n        string Timestamp\n    }\n    DataPolicy {\n        int PolicyID PK\n        string PolicyName\n        string RuleDefinition\n        string IsActive\n        string CreatedAt\n    }\n    DataLineage {\n        int LineageID PK\n        string SourceSystem\n        string TargetSystem\n        string TransformationLogic\n        string UpdatedAt\n    }\n\n    Customer ||--o{ Account : has\n    Customer ||--o{ OnboardingApplication : appliesThrough\n    OnboardingApplication ||--|| IdentityVerification : requires\n    Customer ||--o{ UserSession : initiates\n    Customer ||--o{ Consent : gives\n    Customer }o--|| CustomerSegment : belongsTo\n    OnboardingApplication }o--o{ Customer : creates\n```";
const sanitizedMermaidOutput = sanitizeMermaidClassDiagram(rawMermaidOutput);
const sanitizedDataModelOutput = sanitizeMermaidERDiagram(rawDataModelOutput);

console.log("--- Raw Output CLASS DIAGRAM(for inspection in console) ---");
console.log(rawMermaidOutput); // Look for the ' ' characters if your console reveals them
console.log("--- Raw Output DATA MODEL (for inspection in console) ---");
console.log(rawDataModelOutput); // Look for the ' ' characters if your console reveals them

console.log("--- Sanitized Output (repr-like for inspection) ---");
// Simulate repr() in JavaScript (less direct than Python, but helpful)
console.log(JSON.stringify(sanitizedMermaidOutput)); // This will escape non-ASCII, so you'd see \u00A0 if present
console.log(JSON.stringify(sanitizedDataModelOutput));

// Also log it as a raw string to check visual formatting
console.log("--- Sanitized Output (Raw String) ---");
console.log(sanitizedMermaidOutput);
console.log(sanitizedDataModelOutput);

// Then pass sanitizedMermaidOutput to your Mermaid renderer
*/

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
  /* Class diagram and data model */
  const [classDiagram, setClassDiagram] = useState("");
  const [dataModel, setDataModel] = useState("");

  /* View diagram const definitions*/
  const [archName, setArchName] = useState('');
  const [archSuggestions, setArchSuggestions] = useState([]);

  /* Adding wait for sections in output from AaCAgent */
  const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  const [showPros, setShowPros] = useState(false);
  const [showCons, setShowCons] = useState(false);
  const [showClassDiagram, setShowClassDiagram] = useState(false);
  const [showDataModel, setShowDataModel] = useState(false);

  useEffect(() => {
    if (activeTab === "upload") {
        setShowPros(false);
        setShowCons(false);
        setShowClassDiagram(false);
        setShowDataModel(false);
    }
    const revealSections = async () => {
      if (pros.length > 0) {
        await wait(500); // show after 0.5 sec
        setShowPros(true);
      }
      if (cons.length > 0) {
        await wait(500);
        setShowCons(true);
      }
      if (classDiagram) {
        await wait(1500);
        setShowClassDiagram(true);
      }
      if (dataModel) {
        await wait(1500);
        setShowDataModel(true);
      }
    };

    revealSections();
  }, [activeTab, pros, cons, classDiagram, dataModel]);

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
                'text-wrap': 'wrap',            // ✅ enables wrapping
                'text-max-width': 5,
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
        const reflink = item.r[3]?.reflink;

        if (!addedNodes.has(source)) {
          cy.add({ data: { id: source, label: sourceLabel, trueId: item.n.id } });
          addedNodes.add(source);
        }
        if (!addedNodes.has(target)) {
          cy.add({ data: { id: target, label: targetLabel, trueId: item.m.id } });
          addedNodes.add(target);
        }
        if (!addedEdges.has(edgeId)) {
            cy.add({ data: { id: edgeId, source, target, sourceLabel, targetLabel, label: relType, reflink } });
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

      cy.on('tap', 'edge', (event) => {
              const reflink = event.target.data('reflink');
              if (reflink) {
                window.open(reflink, '_blank'); // Open in new tab
              }
      });

        let tooltip = null;
        let moveListener = null;

        cy.on('mouseover', 'edge', (event) => {
          const edge = event.target;
          const reflink = edge.data('reflink');

          if (!reflink) return;

          // Clean up any existing tooltip
          if (tooltip) tooltip.remove();

          tooltip = document.createElement('div');
          tooltip.innerText = reflink;
          tooltip.style.position = 'absolute';
          tooltip.style.background = '#fff';
          tooltip.style.border = '1px solid #000';
          tooltip.style.padding = '6px';
          tooltip.style.fontSize = '12px';
          tooltip.style.maxWidth = '300px';
          tooltip.style.wordWrap = 'break-word';
          tooltip.style.zIndex = 9999;
          tooltip.style.pointerEvents = 'none';
          tooltip.id = 'cy-tooltip';
          document.body.appendChild(tooltip);

          moveListener = (e) => {
            if (tooltip) {
              tooltip.style.left = e.pageX + 10 + 'px';
              tooltip.style.top = e.pageY + 10 + 'px';
            }
          };

          document.addEventListener('mousemove', moveListener);
        });

        cy.on('mouseout', 'edge', () => {
          if (tooltip) {
            tooltip.remove();
            tooltip = null;
          }

          if (moveListener) {
            document.removeEventListener('mousemove', moveListener);
            moveListener = null;
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
      setClassDiagram('');
      setDataModel('');
      setSummary('');
      setDescription('');
      setPros([]);
      setCons([]);
      setEdges([]);
      setNodes([]);
      setComplexityTable([]);
      setShowClassDiagram(false);
      setShowDataModel(false);
      const res= await axios.post("http://localhost:7001/upload/", formData, {headers: { "Content-Type": "multipart/form-data" },});
      const { mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons, class_diagram, data_model } = res.data;
      const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;
      setMermaidCode(String(cleanCode));
      setSummary(summary);
      setDescription(description);
      setNodes(nodes || []);
      setEdges(edges || []);
      setComplexityTable(complexity_table || []);
      setPros(pros || []);
      setCons(cons || []);
      setClassDiagram(class_diagram || "");
      setDataModel(data_model || "");
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
        setClassDiagram('');
        setDataModel('');
        setSummary('');
        setDescription('');
        setPros([]);
        setCons([]);
        setEdges([]);
        setNodes([]);
        setComplexityTable([]);
        setShowClassDiagram(false);
        setShowDataModel(false);

        const res = await axios.post("http://localhost:7001/process_confluence/", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });

        const { mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons, class_diagram, data_model } = res.data;

        const cleanCode = Array.isArray(mermaid_code) ? mermaid_code[0] : mermaid_code;

        setMermaidCode(String(cleanCode));
        setSummary(summary);
        setDescription(description);
        setNodes(nodes || []);
        setEdges(edges || []);
        setComplexityTable(complexity_table || []);
        setPros(pros || []);
        setCons(cons || []);
        setClassDiagram(class_diagram || "");
        setDataModel(data_model || "");

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
      setClassDiagram('');
      setDataModel('');
      setSummary('');
      setDescription('');
      setPros([]);
      setCons([]);
      setEdges([]);
      setNodes([]);
      setComplexityTable([]);
      setShowClassDiagram(false);
      setShowDataModel(false);

      const res= await axios.get("http://localhost:7001/get_arch_code", { params: { arch_name: archName }});
      const { arch_name, mermaid_code, summary, description, nodes, edges, complexity_table, pros, cons, class_diagram, data_model } = res.data;
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
      setClassDiagram(class_diagram || "");
      setDataModel(data_model || "");

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

                        {summary && (
                            <>
                                <h3>Derived Summary</h3>
                                <p>{summary}</p>
                            </>
                        )}

                        {description && (
                            <>
                                <h3>Derived Description</h3>
                                <p>{description}</p>
                            </>
                        )}

                        {complexityTable.length > 0 && (
                            <>
                                <h3>Derived System Complexity</h3>
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

                        {showPros && (
                            <>
                              <h3>Derived Pros</h3>
                              <ul>
                                {pros.map((item, index) => (
                                  <li key={index}>{item}</li>
                                ))}
                              </ul>
                            </>
                          )}

                        {showCons && (
                            <>
                              <h3>Derived Cons</h3>
                              <ul>
                                {cons.map((item, index) => (
                                  <li key={index}>{item}</li>
                                ))}
                              </ul>
                            </>
                          )}

                        {showClassDiagram && (
                            <>
                              <h3>Recommended Class Diagram</h3>
                              <MermaidRenderer chart={sanitizeMermaidClassDiagram(classDiagram)} />
                            </>
                          )}

                        {showDataModel && (
                            <>
                                <h3>Recommended Data Model</h3>
                                <MermaidRenderer chart={sanitizeMermaidERDiagram(dataModel)} />
                                {dataModel && (
                                  <button className="primary-button"
                                    onClick={() => {
                                      const newWindow = window.open("", "_blank");
                                      const html = `
                                        <html>
                                        <head>
                                          <title>Data Model</title>
                                          <script type="module">
                                            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                                            mermaid.initialize({ startOnLoad: true });
                                          </script>
                                          <style>
                                            body { margin: 0; padding: 1rem; font-family: sans-serif; background: #f9f9f9; }
                                            .mermaid { width: 100%; }
                                          </style>
                                        </head>
                                        <body>
                                          <div class="mermaid">
                                            ${sanitizeMermaidERDiagram(dataModel)}
                                          </div>
                                        </body>
                                        </html>
                                      `;
                                      newWindow.document.write(html);
                                      newWindow.document.close();
                                    }}
                                    style={{ marginTop: '1rem' }}
                                  >
                                    View Data Model in new tab
                                  </button>
                                )}
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