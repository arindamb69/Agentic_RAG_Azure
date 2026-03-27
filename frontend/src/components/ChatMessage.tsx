import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { ThinkingIndicator } from './ThinkingIndicator';
import { User, Bot, Clock, Zap, Copy, Check, Download, Volume2, Headphones } from 'lucide-react';
import clsx from 'clsx';
import { Mermaid } from './Mermaid';
import { PlantUML } from './PlantUML';

export interface Metrics {
    duration_ms: number;
    tokens: number;
}

export interface Message {
    role: 'user' | 'assistant';
    content: string;
    thoughts?: string[];
    metrics?: Metrics;
    isThinking?: boolean;
    metadata?: {
        type: 'file_upload' | 'other';
        fileName?: string;
        fileSize?: number;
    }
}

interface ChatMessageProps {
    message: Message;
}

const CodeBlock: React.FC<{ code: string, className?: string }> = ({ code, className }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group/code my-4 rounded-xl overflow-hidden border border-slate-700 bg-[#1e293b] shadow-md">
            <div className="flex items-center justify-between px-4 py-2 bg-slate-800/50 border-b border-slate-700">
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
                    {className?.replace('language-', '') || 'code'}
                </span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 text-[10px] font-medium text-slate-300 hover:text-white transition-colors"
                >
                    {copied ? (
                        <>
                            <Check size={12} className="text-green-500" />
                            <span className="text-green-500 font-bold">Copied!</span>
                        </>
                    ) : (
                        <>
                            <Copy size={12} />
                            <span>Copy</span>
                        </>
                    )}
                </button>
            </div>
            <pre className={clsx(className, "p-4 overflow-x-auto text-sm leading-relaxed")}>
                <code>{code}</code>
            </pre>
        </div>
    );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';
    const [copied, setCopied] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);

    const copyToClipboard = (text: string, isMain = false) => {
        navigator.clipboard.writeText(text);
        if (isMain) {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const downloadPdf = async () => {
        setIsDownloading(true);
        try {
            const response = await fetch('http://localhost:8000/generate-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ markdown: message.content })
            });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || "PDF generation failed");
            }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `response_${Date.now()}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (error: any) {
            console.error("PDF generation failed", error);
            alert(error.message || "Failed to generate PDF");
        } finally {
            setIsDownloading(false);
        }
    }

    const downloadAudio = async () => {
        setIsDownloading(true);
        try {
            const response = await fetch('http://localhost:8000/generate-audio', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: message.content })
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || "Audio generation failed");
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `speech_${Date.now()}.mp3`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (error: any) {
            console.error("Audio generation failed", error);
            alert(error.message || "Failed to generate audio. Please ensure TTS is configured in the backend.");
        } finally {
            setIsDownloading(false);
        }
    }

    const speakMessage = () => {
        // Cancel any ongoing speech
        window.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(message.content);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.lang = 'en-US';
        
        // Find a good voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.name.includes('Google US English') || v.name.includes('Microsoft Maria'));
        if (preferredVoice) utterance.voice = preferredVoice;

        window.speechSynthesis.speak(utterance);
    }

    return (
        <div className={clsx(
            "group relative flex gap-4 p-5 rounded-2xl transition-all duration-200",
            isUser ? "bg-white shadow-sm border border-slate-100 ml-12" : "bg-blue-50/50 border border-blue-100/50 mr-12"
        )}>
            {/* Main Message Icons */}
            {!isUser && !message.isThinking && (
                <div className="absolute top-4 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all z-10">
                    <button
                        onClick={speakMessage}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg transition-all"
                        title="Read aloud"
                    >
                        <Volume2 size={16} />
                    </button>
                    <button
                        onClick={downloadPdf}
                        disabled={isDownloading}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg transition-all"
                        title="Download as PDF"
                    >
                        {isDownloading ? <Clock size={16} className="animate-spin" /> : <Download size={16} />}
                    </button>
                    <button
                        onClick={downloadAudio}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg transition-all"
                        title="Download Audio"
                    >
                        <Headphones size={16} />
                    </button>
                    <button
                        onClick={() => copyToClipboard(message.content, true)}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg transition-all"
                        title="Copy full message"
                    >
                        {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
                    </button>
                </div>
            )}

            <div className={clsx(
                "flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center shadow-sm",
                isUser ? "bg-slate-800 text-white" : "bg-blue-600 text-white"
            )}>
                {isUser ? <User size={20} /> : <Bot size={20} />}
            </div>

            <div className="flex-1 overflow-hidden">
                <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm text-slate-800 tracking-tight">
                        {isUser ? 'You' : 'Azure AI Assistant'}
                    </span>
                </div>

                {message.thoughts && (
                    <div className="mb-4">
                        <ThinkingIndicator
                            thoughts={message.thoughts}
                            isComplete={!message.isThinking}
                        />
                    </div>
                )}

                <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed font-normal">
                    <ReactMarkdown
                        components={{
                            code({ node, inline, className, children, ...props }: any) {
                                const match = /language-(\w+)/.exec(className || '');
                                const codeString = String(children).replace(/\n$/, '');

                                if (!inline && match && match[1] === 'mermaid') {
                                    return <Mermaid chart={codeString} />;
                                }

                                if (!inline && match && (match[1] === 'plantuml' || match[1] === 'puml')) {
                                    return <PlantUML code={codeString} />;
                                }

                                if (!inline) {
                                    return <CodeBlock code={codeString} className={className} />;
                                }
                                return <code className={className} {...props}>{children}</code>;
                            }
                        }}
                    >
                        {message.metadata?.type === 'file_upload' 
                          ? `📄 File: **${message.metadata.fileName}** (${(message.metadata.fileSize || 0) / 1024 > 1024 ? ((message.metadata.fileSize || 0) / (1024 * 1024)).toFixed(1) + 'MB' : ((message.metadata.fileSize || 0) / 1024).toFixed(1) + 'KB'})\n\n*(Content processed by assistant)*`
                          : message.content}
                    </ReactMarkdown>
                </div>

                {message.metrics && (
                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-4 text-[10px] font-medium uppercase tracking-wider text-slate-400">
                        <span className="flex items-center gap-1.5 bg-slate-100 px-2 py-1 rounded">
                            <Clock size={10} /> {(message.metrics.duration_ms / 1000).toFixed(2)}s Latency
                        </span>
                        <span className="flex items-center gap-1.5 bg-slate-100 px-2 py-1 rounded">
                            <Zap size={10} /> {message.metrics.tokens} Tokens
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};
