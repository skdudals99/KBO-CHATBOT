import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import Message from './Message'
import { Send, Loader, Bot, User } from 'lucide-react'
import './ChatInterface.css'

const API_URL = 'http://localhost:8000'

function ChatInterface() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '안녕하세요! ⚾ KBO 매치업 분석 챗봇입니다.\n\n다음과 같은 질문을 해보세요:\n• 2024년 김광현 vs 최정 매치업 알려줘\n• 양현종이 삼진을 많이 잡을 수 있는 타자는?\n• 2사 만루에서 원태인이 나성범에게 슬라이더를 던지면?',
      timestamp: new Date(),
      source: 'system'
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // 메시지 추가 시 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 포커스 유지
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading])

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!input.trim() || isLoading) return

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        question: input,
        use_rag: true
      })

      const assistantMessage = {
        role: 'assistant',
        content: response.data.answer,
        timestamp: new Date(),
        source: response.data.source,
        sources: response.data.sources || [],
        debug_info: response.data.debug_info
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error:', error)
      
      const errorMessage = {
        role: 'assistant',
        content: '죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.',
        timestamp: new Date(),
        source: 'error',
        isError: true
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <div className="header-content">
          <Bot size={32} className="header-icon" />
          <div className="header-text">
            <h1>⚾ KBO 매치업 챗봇</h1>
            <p>규칙 기반 엔진 + RAG 하이브리드 시스템</p>
          </div>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}
        
        {isLoading && (
          <div className="message assistant loading">
            <div className="message-avatar">
              <Bot size={20} />
            </div>
            <div className="message-content">
              <div className="loading-indicator">
                <Loader className="spinner" size={16} />
                <span>답변 생성 중...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="input-container">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="질문을 입력하세요... (Shift+Enter로 줄바꿈)"
            rows={1}
            disabled={isLoading}
          />
          <button 
            type="submit" 
            disabled={!input.trim() || isLoading}
            className="send-button"
          >
            <Send size={20} />
          </button>
        </div>
      </form>
    </div>
  )
}

export default ChatInterface