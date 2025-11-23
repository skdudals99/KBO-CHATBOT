import React from 'react'
import ReactMarkdown from 'react-markdown'
import { Bot, User } from 'lucide-react'
import './Message.css'

function Message({ message }) {
  const isUser = message.role === 'user'
  const isError = message.isError

  const getSourceBadge = (source) => {
    const badges = {
      rule: { text: '규칙 엔진', color: '#10b981' },
      rag: { text: 'RAG', color: '#3b82f6' },
      hybrid: { text: '하이브리드', color: '#8b5cf6' },
      system: { text: '시스템', color: '#6b7280' },
      error: { text: '오류', color: '#ef4444' }
    }

    const badge = badges[source] || badges.system

    return (
      <span 
        className="source-badge" 
        style={{ backgroundColor: badge.color }}
      >
        {badge.text}
      </span>
    )
  }

  return (
    <div className={`message ${isUser ? 'user' : 'assistant'} ${isError ? 'error' : ''}`}>
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      
      <div className="message-content">
        {!isUser && message.source && (
          <div className="message-meta">
            {getSourceBadge(message.source)}
            <span className="message-time">
              {message.timestamp.toLocaleTimeString('ko-KR', { 
                hour: '2-digit', 
                minute: '2-digit' 
              })}
            </span>
          </div>
        )}
        
        <div className="message-text">
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <details>
              <summary>📚 참고 문서 ({message.sources.length}개)</summary>
              <div className="sources-list">
                {message.sources.map((source, idx) => (
                  <div key={idx} className="source-item">
                    <strong>{source.season}시즌</strong> - {source.pitcher} vs {source.batter}
                    <p className="source-preview">{source.content_preview}</p>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  )
}

export default Message