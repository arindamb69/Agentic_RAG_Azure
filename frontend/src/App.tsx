import { useState, useRef, useEffect } from 'react'
import {
  Plus, MessageSquare, Settings, ChevronLeft, ChevronRight,
  Send, Upload, Mic, Sparkles, Trash2, Copy, Download
} from 'lucide-react'
import { ChatMessage, type Message } from './components/ChatMessage'
import clsx from 'clsx'

interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}

const DEFAULT_QUESTIONS = [
  'Services available in Unified Data Platform',
  'Top 3 fastest car in collection',
  'Top 3 AI Buzzword Topics'
];

function App() {
  const [chats, setChats] = useState<Chat[]>(() => {
    const saved = localStorage.getItem('azure-rag-chats');
    return saved ? JSON.parse(saved) : [];
  })
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isFileProcessing, setIsFileProcessing] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('azure-openai-api-key') || '')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Sync current chat messages when chatId changes
  useEffect(() => {
    if (currentChatId) {
      const chat = chats.find(c => c.id === currentChatId);
      if (chat) {
        setMessages(chat.messages);
      }
    } else {
      setMessages([]);
    }
  }, [currentChatId])

  // Persist chats to localStorage
  useEffect(() => {
    localStorage.setItem('azure-rag-chats', JSON.stringify(chats));
  }, [chats])

  useEffect(() => {
    localStorage.setItem('azure-openai-api-key', apiKey);
  }, [apiKey])

  const startNewChat = () => {
    setCurrentChatId(null);
    setMessages([]);
    setInput('');
  }

  const deleteChat = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChats(prev => prev.filter(c => c.id !== id));
    if (currentChatId === id) {
      startNewChat();
    }
  }

  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<any>(null)

  useEffect(() => {
    // Initialize Speech Recognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput(prev => prev + (prev ? ' ' : '') + transcript);
        setIsListening(false);
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }
  }, [])

  const toggleVoiceInput = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition not supported in this browser.");
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
      setIsListening(true);
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsFileProcessing(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();

      if (data.error) {
        alert(data.error);
      } else {
        // Automatically ask the agent about the file
        const prefix = `I uploaded a file named "${file.name}". `;
        const fileQuery = prefix + (data.text ? `Here is the extracted content / insight: \n\n${data.text} ` : "Please analyze this file.");

        // Add a message with metadata so the UI can render it as a file
        const userMessage: Message = { 
          role: 'user', 
          content: fileQuery,
          metadata: {
            type: 'file_upload',
            fileName: file.name,
            fileSize: file.size
          }
        };
        
        // Use the core submit logic
        await handleMessageSubmit(userMessage);
      }
    } catch (error) {
      console.error("Upload failed", error);
      alert("File upload failed");
    } finally {
      setIsFileProcessing(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  const handleSubmit = async (e?: React.FormEvent, overrideInput?: string) => {
    if (e) e.preventDefault()
    const queryStr = overrideInput || input
    if (!queryStr.trim() || isLoading) return

    const userMessage: Message = { role: 'user', content: queryStr }
    await handleMessageSubmit(userMessage)
  }

  const handleMessageSubmit = async (userMessage: Message) => {
    if (isLoading) return
    
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setIsLoading(true)

    // Save/Update chat in history
    let activeId = currentChatId;
    if (!activeId) {
      activeId = Date.now().toString();
      const newChat: Chat = {
        id: activeId,
        title: userMessage.content.split('\n')[0].slice(0, 40) + '...',
        messages: updatedMessages,
        createdAt: Date.now()
      };
      setChats(prev => [newChat, ...prev]);
      setCurrentChatId(activeId);
    } else {
      setChats(prev => prev.map(c =>
        c.id === activeId ? { ...c, messages: updatedMessages } : c
      ));
    }

    // Add placeholder assistant message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: '',
      thoughts: [],
      isThinking: true
    }])

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey // Send API key to backend if needed
        },
        body: JSON.stringify({
          query: userMessage.content,
          messages: messages,
          api_key: apiKey // Or in body
        })
      })

      if (!response.body) throw new Error('No response body')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim()
            if (!jsonStr) continue

            try {
              const data = JSON.parse(jsonStr)

              setMessages(prev => {
                const newMessages = [...prev]
                const lastIdx = newMessages.length - 1
                const lastMsg = { ...newMessages[lastIdx] }

                if (data.type === 'thought') {
                  lastMsg.thoughts = [...(lastMsg.thoughts || []), data.content]
                } else if (data.type === 'chunk') {
                  lastMsg.content += data.content
                } else if (data.type === 'metrics') {
                  lastMsg.metrics = {
                    duration_ms: data.duration_ms,
                    tokens: data.tokens
                  }
                  console.log("Setting metrics:", lastMsg.metrics)
                } else if (data.type === 'complete') {
                  lastMsg.isThinking = false
                  // If metrics were passed with complete
                  if (data.tokens || data.duration_ms) {
                    lastMsg.metrics = {
                      duration_ms: data.duration_ms || (lastMsg.metrics?.duration_ms || 0),
                      tokens: data.tokens || (lastMsg.metrics?.tokens || 0)
                    }
                  }
                }

                newMessages[lastIdx] = lastMsg

                // Keep chats updated with final assistant message
                setChats(prevChats => prevChats.map(c =>
                  c.id === activeId ? { ...c, messages: newMessages } : c
                ));

                return newMessages
              })
            } catch (e) {
              console.error("Error parsing JSON", e)
            }
          }
        }
      }
    } catch (error) {
      console.error(error)
      const errorMsg: Message = { role: 'assistant', content: 'Sorry, I encountered an error.' }
      setMessages(prev => [...prev, errorMsg])
      setChats(prev => prev.map(c =>
        c.id === activeId ? { ...c, messages: [...c.messages, errorMsg] } : c
      ));
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans relative">
      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-300">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="p-8">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-xl text-blue-600">
                    <Settings size={22} />
                  </div>
                  <h3 className="text-xl font-bold text-slate-900">Settings</h3>
                </div>
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400"
                >
                  <ChevronRight size={20} className="rotate-90" />
                </button>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Azure OpenAI API Key</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your API key..."
                    className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none font-medium"
                  />
                  <p className="text-[10px] text-slate-400 mt-2 flex items-center gap-1">
                    <Sparkles size={10} className="text-blue-500" />
                    Key is stored locally in your browser
                  </p>
                </div>

                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-200 transition-all active:scale-[0.98]"
                >
                  Save & Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <aside className={clsx(
        "bg-slate-900 text-slate-300 flex flex-col transition-all duration-300 ease-in-out border-r border-slate-800 shrink-0",
        isSidebarOpen ? "w-72" : "w-0 opacity-0 -translate-x-full"
      )}>
        <div className="p-4 flex flex-col h-full overflow-hidden">
          <button
            onClick={startNewChat}
            className="flex items-center gap-3 w-full p-3 rounded-xl border border-slate-700 hover:bg-slate-800 transition-all text-white font-medium mb-6 group shadow-sm"
          >
            <Plus size={20} className="text-blue-400 group-hover:rotate-90 transition-transform duration-300" />
            <span>New Chat</span>
          </button>

          <div className="flex-1 overflow-y-auto space-y-2 -mx-2 px-2 scrollbar-thin scrollbar-thumb-slate-700">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-3 px-2">Recent Conversations</div>
            {chats.map(chat => (
              <div
                key={chat.id}
                onClick={() => setCurrentChatId(chat.id)}
                className={clsx(
                  "group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all",
                  currentChatId === chat.id ? "bg-slate-800 text-white shadow-inner" : "hover:bg-slate-800/50"
                )}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <MessageSquare size={16} className={currentChatId === chat.id ? "text-blue-400" : "text-slate-500"} />
                  <span className="text-sm truncate">{chat.title}</span>
                </div>
                <button
                  onClick={(e) => deleteChat(chat.id, e)}
                  className="p-1 opacity-0 group-hover:opacity-100 hover:bg-slate-700 rounded transition-all"
                >
                  <Trash2 size={14} className="text-slate-500 hover:text-red-400" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-auto pt-4 border-t border-slate-800 space-y-1">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="flex items-center gap-3 w-full p-3 rounded-xl hover:bg-slate-800 transition-all text-sm"
            >
              <Settings size={18} />
              <span>Settings</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative overflow-hidden bg-white">
        {/* Toggle Sidebar Button */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={clsx(
            "fixed top-4 left-4 z-50 p-2 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50 transition-all",
            !isSidebarOpen && "left-4"
          )}
          style={{ marginLeft: isSidebarOpen ? 'calc(18rem + 1rem)' : '0', transition: 'margin-left 300ms' }}
        >
          {isSidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>

        {/* Header - Minimalist */}
        <header className="px-6 py-4 flex items-center justify-between border-b border-slate-100 bg-white/80 backdrop-blur-md sticky top-0 z-10 h-16">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg text-white shadow-sm">
              <Sparkles size={20} />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 tracking-tight leading-none">Azure Agentic RAG</h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-600 mt-1">Enterprise AI</p>
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto scroll-smooth">
          <div className="max-w-4xl mx-auto p-4 md:p-8 space-y-8">
            {messages.length === 0 ? (
              <div className="py-20 flex flex-col items-center justify-center text-center animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="w-20 h-20 bg-blue-100 rounded-3xl flex items-center justify-center mb-8 shadow-inner">
                  <Sparkles size={40} className="text-blue-600" />
                </div>
                <h2 className="text-4xl font-black text-slate-900 mb-4 tracking-tight">
                  Welcome back to <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Enterprise AI</span>
                </h2>
                <p className="text-slate-500 text-lg max-w-xl mb-12 font-medium">
                  Your intelligent companion for document retrieval, data analysis, and technical reasoning.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full">
                  {DEFAULT_QUESTIONS.map((question, i) => (
                    <div key={i} className="group relative">
                      <button
                        onClick={() => handleSubmit(undefined, question)}
                        className="w-full h-full p-6 text-left bg-white border border-slate-100 rounded-2xl shadow-sm hover:shadow-md hover:border-blue-200 transition-all overflow-hidden"
                      >
                        <div className="absolute top-0 right-0 p-3 text-blue-100 group-hover:text-blue-500 transition-colors">
                          <MessageSquare size={24} />
                        </div>
                        <p className="text-slate-700 font-semibold relative z-10 leading-snug pr-8">{question}</p>
                        <p className="text-slate-400 text-xs mt-3 relative z-10">Click to ask agent</p>
                      </button>

                      {/* Action buttons for predefined questions */}
                      <div className="absolute bottom-4 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all z-20">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard.writeText(question);
                            alert("Question copied!");
                          }}
                          className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-slate-50 rounded-lg transition-all"
                          title="Copy question"
                        >
                          <Copy size={14} />
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const response = await fetch('http://localhost:8000/generate-pdf', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ markdown: question })
                              });
                              const blob = await response.blob();
                              const url = window.URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = `question_${Date.now()}.pdf`;
                              a.click();
                            } catch (err) {
                              alert("Failed to download PDF");
                            }
                          }}
                          className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-slate-50 rounded-lg transition-all"
                          title="Download as PDF"
                        >
                          <Download size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <ChatMessage key={idx} message={msg} />
              ))
            )}
            <div ref={messagesEndRef} className="h-4" />
          </div>
        </div>

        {/* Input Area */}
        <div className="p-4 md:p-8 bg-gradient-to-t from-white via-white to-transparent">
          <div className="max-w-4xl mx-auto relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl blur opacity-10 group-focus-within:opacity-25 transition duration-500"></div>
            <form onSubmit={handleSubmit} className="relative flex items-end gap-2 bg-white rounded-2xl border border-slate-200 shadow-lg p-2 transition-all focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-50">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                className="hidden"
                accept=".txt,.md,.pdf,.png,.jpg,.jpeg,.mp3,.wav,.mp4"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isFileProcessing}
                className={clsx(
                  "p-3 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all",
                  isFileProcessing && "animate-pulse text-blue-600"
                )}
                title="Upload files"
              >
                <Upload size={20} />
              </button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder="Message Azure Agent..."
                className="flex-1 max-h-48 p-3 bg-transparent outline-none text-slate-800 placeholder:text-slate-400 resize-none font-medium"
                rows={1}
                disabled={isLoading}
              />
              <div className="flex items-center gap-1 pr-1 pb-1">
                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  className={clsx(
                    "p-3 rounded-xl transition-all",
                    isListening ? "bg-red-100 text-red-600 animate-pulse" : "text-slate-400 hover:text-red-600 hover:bg-red-50"
                  )}
                  title={isListening ? "Stop listening" : "Voice input"}
                >
                  <Mic size={20} />
                </button>
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-20 disabled:grayscale transition-all shadow-md active:scale-95"
                >
                  <Send size={20} />
                </button>
              </div>
            </form>
            <div className="flex items-center justify-center gap-6 mt-4 opacity-50 grayscale hover:grayscale-0 hover:opacity-100 transition-all duration-700">
              <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft" className="h-4" />
              <div className="h-3 w-px bg-slate-200"></div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none">Powered by Azure OpenAI & Search</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App

