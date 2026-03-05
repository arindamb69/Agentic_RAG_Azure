import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
    startOnLoad: true,
    theme: 'base',
    themeVariables: {
        primaryColor: '#3b82f6',
        primaryTextColor: '#fff',
        primaryBorderColor: '#2563eb',
        lineColor: '#64748b',
        secondaryColor: '#f8fafc',
        tertiaryColor: '#fff',
    },
    securityLevel: 'loose',
});

interface MermaidProps {
    chart: string;
}

export const Mermaid: React.FC<MermaidProps> = ({ chart }) => {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (ref.current && chart) {
            // 1. Basic Cleaning
            let sanitizedChart = chart.trim();
            sanitizedChart = sanitizedChart.replace(/```mermaid\n?/g, '').replace(/```/g, '').trim();

            if (sanitizedChart.toLowerCase().startsWith('mermaid')) {
                sanitizedChart = sanitizedChart.replace(/^mermaid\s+/i, '').trim();
            }

            // 2. Find valid start keyword
            const validKeywords = ['graph', 'flowchart', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'erDiagram', 'journey', 'gantt', 'pie', 'quadrantChart', 'requirementDiagram', 'gitGraph', 'C4Context', 'C4Container', 'C4Component', 'C4Dynamic', 'C4Deployment'];
            const lines = sanitizedChart.split('\n');
            const startIndex = lines.findIndex(line => validKeywords.some(kw => line.trim().startsWith(kw)));
            if (startIndex !== -1) {
                sanitizedChart = lines.slice(startIndex).join('\n').trim();
            }

            // 3. ADVANCED HEALING (Simplified)
            // Just ensure subgraphs have spaces before brackets if they were missed.
            const processedLines = sanitizedChart.split('\n').map(line => {
                let l = line.trim();
                if (l.startsWith('subgraph')) {
                    if (l.includes('[')) {
                        return l.replace(/subgraph\s+([A-Za-z0-9_-]+)\s*\[\s*"?([^"\]]+)"?\s*\]/i, 'subgraph $1 [$2]');
                    }
                }
                return l;
            });

            sanitizedChart = processedLines.join('\n');

            const renderChart = async () => {
                try {
                    if (!ref.current) return;
                    ref.current.innerHTML = '';
                    ref.current.removeAttribute('data-processed');

                    const uniqueId = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
                    const { svg } = await mermaid.render(uniqueId, sanitizedChart);
                    if (ref.current) {
                        ref.current.innerHTML = svg;
                    }
                } catch (error) {
                    console.error("Mermaid Render Error", error);
                    if (ref.current) {
                        ref.current.innerHTML = `<div class="p-4 bg-red-50 text-red-600 rounded text-[10px] shadow-inner overflow-auto w-full border border-red-200">
              <div class="font-bold mb-1 flex items-center gap-2">
                <span class="bg-red-600 text-white px-1.5 py-0.5 rounded-sm uppercase">Syntax Fix Applied</span>
              </div>
              <pre class="whitespace-pre-wrap mb-2 font-mono text-xs text-red-700 bg-red-100/30 p-2 rounded border border-red-100">${String(error).split('\n')[0]}</pre>
              <div class="text-slate-500 mb-1 font-semibold uppercase tracking-widest text-[8px]">Processed Code:</div>
              <pre class="bg-white/80 p-2 rounded font-mono text-[9px] border border-slate-200 max-h-[300px] overflow-y-auto">${sanitizedChart}</pre>
            </div>`;
                    }
                }
            };

            renderChart();
        }
    }, [chart]);

    return (
        <div className="mermaid-container bg-white p-6 rounded-xl border border-slate-200 my-4 flex flex-col items-center justify-center overflow-auto shadow-sm max-h-[1000px] min-h-[150px] w-full">
            <div ref={ref} className="mermaid w-full flex justify-center">
                <div className="animate-pulse text-slate-300 text-xs text-center py-10">Constructing diagram...</div>
            </div>
        </div>
    );
};
