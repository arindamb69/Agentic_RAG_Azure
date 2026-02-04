import React, { useState } from 'react';
import { ChevronDown, ChevronRight, BrainCircuit } from 'lucide-react';

interface ThinkingIndicatorProps {
    thoughts: string[];
    isComplete: boolean;
}

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({ thoughts, isComplete }) => {
    const [isOpen, setIsOpen] = useState(true);

    if (thoughts.length === 0) return null;

    return (
        <div className="my-2 border border-blue-100 rounded-lg bg-blue-50/50 overflow-hidden">
            <div
                className="flex items-center gap-2 p-2 cursor-pointer hover:bg-blue-100/50 transition-colors"
                onClick={() => setIsOpen(!isOpen)}
            >
                {isOpen ? <ChevronDown size={16} className="text-blue-500" /> : <ChevronRight size={16} className="text-blue-500" />}
                <BrainCircuit size={16} className="text-blue-500" />
                <span className="text-xs font-semibold text-blue-700">
                    {isComplete ? `Processed ${thoughts.length} steps` : "Thinking..."}
                </span>
            </div>

            {isOpen && (
                <div className="p-2 pt-0 max-h-60 overflow-y-auto font-mono text-xs space-y-1">
                    {thoughts.map((thought, idx) => (
                        <div key={idx} className="text-slate-600 border-l-2 border-blue-200 pl-2">
                            {thought}
                        </div>
                    ))}
                    {!isComplete && (
                        <div className="flex items-center gap-1 text-slate-400 pl-2 animate-pulse">
                            <span className="w-1 h-1 bg-current rounded-full"></span>
                            <span className="w-1 h-1 bg-current rounded-full"></span>
                            <span className="w-1 h-1 bg-current rounded-full"></span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
