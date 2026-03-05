import mermaid from 'mermaid';

const testCode = `
flowchart LR
subgraph Clients
U1["Web App User"]
U2["API Client"]
end

%% Edge / Entry
GW["API Gateway / Frontend Backend"]

%% Orchestrator & Agents
subgraph Agent_Platform [AI Agent Platform]
ORCH["Orchestrator Agent"]

subgraph SubAgents [Specialized Sub-Agents]
A1["Data Agent"]
end
end
`;

async function run() {
    mermaid.initialize({ startOnLoad: false });
    try {
        await mermaid.parse(testCode);
        console.log("Success");
    } catch (e) {
        console.log("Fail:", e.message);
    }
}
run();
