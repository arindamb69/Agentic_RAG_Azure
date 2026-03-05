import mermaid from 'mermaid';
import { JSDOM } from 'jsdom';

console.log("Mermaid version:"); // Should be 11.12.3 or something string? Wait, it has a version property? It doesn't matter.

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="mermaid"></div></body></html>');
global.window = dom.window;
global.document = dom.window.document;

async function run() {
    mermaid.initialize({ startOnLoad: false });

    const chartQuoted = 'flowchart LR\nsubgraph CH ["Sales Channels"]\nW["Web App"]\nend';
    const chartUnquoted = 'flowchart LR\nsubgraph CH [Sales Channels]\nW["Web App"]\nend';
    const chartUser = 'flowchart LR\nsubgraph Agent_Platform [AI Agent Platform]\nORCH["Orchestrator Agent"]\nsubgraph SubAgents [Specialized Sub-Agents]\nA1["Data Agent"]\nend\nend';

    try {
        await mermaid.parse(chartQuoted);
        console.log("Quoted: SUCCESS");
    } catch (e) {
        console.log("Quoted: FAIL -", e.message);
    }

    try {
        await mermaid.parse(chartUnquoted);
        console.log("Unquoted: SUCCESS");
    } catch (e) {
        console.log("Unquoted: FAIL -", e.message);
    }

    try {
        await mermaid.parse(chartUser);
        console.log("User: SUCCESS");
    } catch (e) {
        console.log("User: FAIL -", e.message);
    }
}
run();
