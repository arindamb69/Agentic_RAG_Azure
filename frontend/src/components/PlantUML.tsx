import React from 'react';
import pako from 'pako';

interface PlantUMLProps {
    code: string;
}

export const PlantUML: React.FC<PlantUMLProps> = ({ code }) => {
    try {
        // Kroki expects the source to be:
        // 1. UTF-8 encoded
        // 2. Compressed using zlib (deflate)
        // 3. Base64 URL Safe encoded

        const data = new TextEncoder().encode(code);
        const compressed = pako.deflateRaw(data, { level: 9 });

        // Robust Base64 conversion
        let binary = '';
        const bytes = new Uint8Array(compressed);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);

        // Make it URL safe (Base64url)
        const encoded = base64
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=+$/, '');

        const url = `https://kroki.io/plantuml/svg/${encoded}`;

        return (
            <div className="plantuml-container bg-white p-4 rounded-xl border border-slate-200 my-4 flex flex-col items-center shadow-sm max-w-full overflow-hidden">
                <img
                    src={url}
                    alt="PlantUML Diagram"
                    className="max-w-full h-auto"
                    onError={(e) => {
                        (e.target as HTMLImageElement).parentElement!.innerHTML = '<div class="p-4 text-red-500 text-xs">Error rendering PlantUML. Check your syntax.</div>';
                    }}
                />
                <div className="mt-2 text-[10px] text-slate-400 font-mono italic">Rendered via Kroki (PlantUML/C4)</div>
            </div>
        );
    } catch (err) {
        return (
            <div className="p-4 bg-red-50 text-red-600 rounded border border-red-200 my-4 text-xs">
                Error Encoding Diagram: {String(err)}
            </div>
        );
    }
};
