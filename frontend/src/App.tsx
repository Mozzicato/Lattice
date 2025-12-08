import React, { useState, useEffect, useRef } from 'react';
import MessageRenderer from './MessageRenderer';
import './App.css';
import { api, Session, SessionOverview, Document } from './api';

interface Message {
  role: 'user' | 'ai';
  content: string;
}

function App() {
  const [stage, setStage] = useState<'upload' | 'processing' | 'session'>('upload');
  const [session, setSession] = useState<Session | null>(null);
  const [overview, setOverview] = useState<SessionOverview | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [rewrittenNote, setRewrittenNote] = useState<string | null>(null);
  const [noteInfo, setNoteInfo] = useState<{pageCount: number; imageCount: number} | null>(null);
  const [isRewritingNote, setIsRewritingNote] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileSelect = async (file: File) => {
    if (!file) return;
    
    setIsLoading(true);
    setStage('processing');
    
    try {
      console.log('Uploading file:', file.name);
      const uploadResult = await api.uploadDocument(file);
      console.log('Upload result:', uploadResult);
      
      // Poll for document completion
      let attempts = 0;
      const maxAttempts = 120; // 2 minutes
      
      console.log('Starting to poll for document status...');
      while (attempts < maxAttempts) {
        const doc = await api.getDocument(uploadResult.document_id);
        console.log(`Poll attempt ${attempts + 1}: status =`, doc.doc_metadata?.status);
        
        if (doc.doc_metadata?.status === 'ready_for_learning' || 
            doc.doc_metadata?.status === 'completed') {
          await startLearningSession(doc.id);
          break;
        }
        
        if (doc.doc_metadata?.status === 'failed') {
          alert('Document processing failed. Please try again.');
          setStage('upload');
          setIsLoading(false);
          return;
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
      
      if (attempts >= maxAttempts) {
        alert('Document processing timeout. Please try again.');
        setStage('upload');
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to upload document';
      alert(`Upload failed: ${errorMsg}`);
      setStage('upload');
    }
    
    setIsLoading(false);
  };

  const startLearningSession = async (documentId: string) => {
    try {
      const newSession = await api.startSession(documentId);
      setSession(newSession);
      
      const sessionOverview = await api.getSessionOverview(newSession.session_id);
      setOverview(sessionOverview);
      
      setStage('session');
      
      // Add welcome message
      setMessages([{
        role: 'ai',
        content: `Welcome! I've processed **${sessionOverview.document.filename}**. 

I found:
- ${sessionOverview.concepts.length} key concepts
- ${sessionOverview.equations.length} equations
- ${sessionOverview.sections.length} sections

Feel free to ask me anything about this document!`
      }]);
    } catch (error) {
      console.error('Session error:', error);
      alert('Failed to start learning session');
    }
  };

  const handleAskQuestion = async () => {
    if (!currentQuestion.trim() || !session || isLoading) return;
    
    const question = currentQuestion.trim();
    setCurrentQuestion('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setIsLoading(true);
    
    try {
      const response = await api.askQuestion(session.session_id, question);
      setMessages(prev => [...prev, { role: 'ai', content: response.answer }]);
    } catch (error: any) {
      console.error('Question error:', error);
      const errorDetail = error.response?.data?.detail || 'I encountered an error. Please try again.';
      setMessages(prev => [...prev, { 
        role: 'ai', 
        content: `Sorry, ${errorDetail}` 
      }]);
    }
    
    setIsLoading(false);
  };

  const handleRewriteNotes = async () => {
    if (!overview?.document.id || isRewritingNote) return;
    
    setIsRewritingNote(true);
    try {
      const result = await api.rewriteNotes(overview.document.id);
      setRewrittenNote(result.formatted_content);
      setNoteInfo({
        pageCount: result.page_count,
        imageCount: result.image_count
      });
      setShowNotes(true);
    } catch (error: any) {
      console.error('Note rewrite error:', error);
      alert('Failed to rewrite notes: ' + (error.response?.data?.detail || error.message));
    }
    setIsRewritingNote(false);
  };

  const handleDownloadNotes = async () => {
    if (!overview?.document.id) return;
    
    try {
      const blob = await api.downloadNotes(overview.document.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${overview.document.filename}_formatted.md`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download error:', error);
      alert('Failed to download notes');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🔬 Lattice</h1>
        <p>AI-Powered Learning Platform</p>
      </header>

      <main className="main-content">
        {stage === 'upload' && (
          <div className="upload-container">
            <div 
              className={`upload-zone ${isDragging ? 'dragging' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="upload-icon">📄</div>
              <h2>Upload Your Document</h2>
              <p>Drag & drop a PDF or text file here</p>
              <p style={{ fontSize: '0.9rem', marginTop: '10px' }}>or click to browse</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="file-input"
              accept=".pdf,.txt"
              onChange={(e) => e.target.files && handleFileSelect(e.target.files[0])}
            />
          </div>
        )}

        {stage === 'processing' && (
          <div className="processing">
            <div className="spinner"></div>
            <h2>Processing Your Document...</h2>
            <p>Scanning content, extracting equations, and analyzing with AI</p>
            <p style={{ fontSize: '0.9rem', color: '#999', marginTop: '20px' }}>
              This may take a minute for larger documents
            </p>
          </div>
        )}

        {stage === 'session' && overview && (
          <div className="session-container">
            <aside className="sidebar">
              <h3>📚 Document Info</h3>
              <div className="stats">
                <div className="stat-item">
                  <span className="stat-value">{overview.concepts.length}</span>
                  <span className="stat-label">Concepts</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{overview.equations.length}</span>
                  <span className="stat-label">Equations</span>
                </div>
              </div>

              <h3 style={{ marginTop: '30px' }}>🧠 Key Concepts</h3>
              <ul className="concept-list">
                {overview.concepts.slice(0, 5).map((concept, i) => (
                  <li key={i} className="concept-item">
                    <span className="concept-term">{concept.term}</span>
                    <span className="concept-def">{concept.definition}</span>
                  </li>
                ))}
              </ul>

              <div className="notes-section">
                <h3 style={{ marginTop: '30px' }}>📝 Your Notes</h3>
                <button 
                  className="rewrite-btn"
                  onClick={handleRewriteNotes}
                  disabled={isRewritingNote}
                >
                  {isRewritingNote ? '✨ Rewriting...' : '✨ Beautify My Notes'}
                </button>
                {rewrittenNote && (
                  <button 
                    className="download-btn"
                    onClick={handleDownloadNotes}
                  >
                    ⬇️ Download
                  </button>
                )}
              </div>
            </aside>

            {showNotes && rewrittenNote ? (
              <div className="notes-viewer">
                <div className="notes-header">
                  <h2>📝 Formatted Notes</h2>
                  {noteInfo && (
                    <span className="note-stats">
                      {noteInfo.pageCount} pages • {noteInfo.imageCount} images
                    </span>
                  )}
                  <button 
                    className="close-notes-btn"
                    onClick={() => setShowNotes(false)}
                  >
                    ← Back to Chat
                  </button>
                </div>
                <div className="notes-content">
                  <MessageRenderer content={rewrittenNote} />
                </div>
              </div>
            ) : (
              <div className="chat-container">
                <div className="chat-messages">
                  {messages.map((msg, i) => (
                    <div key={i} className={`message ${msg.role}`}>
                      <div className="message-label">
                        {msg.role === 'user' ? '👤 You' : '🤖 AI Tutor'}
                      </div>
                      <div className="message-content">
                        <MessageRenderer content={msg.content} />
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="message ai">
                      <div className="message-label">🤖 AI Tutor</div>
                      <div className="message-content">Thinking...</div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <div className="chat-input-container">
                  <input
                    type="text"
                    className="chat-input"
                    placeholder="Ask a question about the document..."
                    value={currentQuestion}
                    onChange={(e) => setCurrentQuestion(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAskQuestion()}
                    disabled={isLoading}
                  />
                  <button 
                    className="send-button"
                    onClick={handleAskQuestion}
                    disabled={isLoading || !currentQuestion.trim()}
                  >
                    Send
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
