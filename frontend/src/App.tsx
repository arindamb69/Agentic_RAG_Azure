import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles } from 'lucide-react'
import { ChatMessage, type Message } from './components/ChatMessage'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Add placeholder assistant message
    const botMessageId = Date.now()
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: '',
      thoughts: [],
      isThinking: true
    }])

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage.content, messages: messages })
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

        // Process all complete lines
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
                const lastMsg = { ...newMessages[lastIdx] } // Shallow copy to avoid mutation of prev state

                if (data.type === 'thought') {
                  lastMsg.thoughts = [...(lastMsg.thoughts || []), data.content]
                } else if (data.type === 'chunk') {
                  lastMsg.content += data.content
                } else if (data.type === 'metrics') {
                  lastMsg.metrics = {
                    duration_ms: data.duration_ms,
                    tokens: data.tokens
                  }
                  lastMsg.isThinking = false
                } else if (data.type === 'complete') {
                  lastMsg.isThinking = false
                }

                newMessages[lastIdx] = lastMsg
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
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error.' }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-blue-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
        <div className="p-2 bg-blue-600 rounded-lg text-white">
          <Sparkles size={24} />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-900 leading-none">Azure Agentic RAG</h1>
          <p className="text-sm text-slate-500 mt-1">Enterprise Intelligent Assistant</p>
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div className="max-w-md p-8 bg-white rounded-2xl shadow-sm border border-slate-100">
              <Sparkles size={48} className="text-blue-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-slate-900 mb-2">How can I help you today?</h2>
              <p className="text-slate-600">
                I can help you search enterprise documents, analyze data, and perform complex reasoning tasks.
              </p>
              <div className="grid grid-cols-2 gap-2 mt-6">
                {['Search policies', 'Analyze sales data', 'Draft an email', 'Summarize meeting'].map(action => (
                  <button
                    key={action}
                    onClick={() => setInput(action)}
                    className="p-2 text-sm bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg transition-colors text-left"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-slate-200 p-4 md:p-6 sticky bottom-0">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything..."
            className="w-full p-4 pr-12 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none shadow-sm text-slate-800 placeholder:text-slate-400"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="absolute right-3 top-3 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={18} />
          </button>
        </form>
        <div className="text-center mt-2 text-xs text-slate-400">
          Powered by Azure OpenAI & Azure AI Search
        </div>
      </div>
    </div>
  )
}

export default App
