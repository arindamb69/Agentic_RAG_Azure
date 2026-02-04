import React from 'react';
import ReactMarkdown from 'react-markdown';
import { ThinkingIndicator } from './ThinkingIndicator';
import { User, Bot, Clock, Zap } from 'lucide-react';
import clsx from 'clsx';

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
}

interface ChatMessageProps {
    message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';

    return (
        <div className={clsx("flex gap-4 p-4 rounded-xl", isUser ? "bg-white" : "bg-white/80")}>
            <div className={clsx(
                "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                isUser ? "bg-slate-200 text-slate-600" : "bg-blue-600 text-white"
            )}>
                {isUser ? <User size={18} /> : <Bot size={18} />}
            </div>

            <div className="flex-1 overflow-hidden">
                <div className="font-semibold text-sm text-slate-900 mb-1">
                    {isUser ? 'You' : 'Azure Agent'}
                </div>

                {message.thoughts && (
                    <ThinkingIndicator
                        thoughts={message.thoughts}
                        isComplete={!message.isThinking}
                    />
                )}

                <div className="prose prose-sm prose-slate max-w-none text-slate-700 leading-relaxed">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.metrics && (
                    <div className="mt-2 text-xs text-slate-400 flex items-center gap-3 bg-slate-50 inline-flex px-2 py-1 rounded border border-slate-100">
                        <span className="flex items-center gap-1">
                            <Clock size={12} /> {(message.metrics.duration_ms / 1000).toFixed(2)}s
                        </span>
                        <span className="flex items-center gap-1">
                            <Zap size={12} /> {message.metrics.tokens} tokens
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};
