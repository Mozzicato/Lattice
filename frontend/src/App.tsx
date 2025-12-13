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
  const [beautifiedContent, setBeautifiedContent] = useState<string | null>(null);
  const [beautificationInfo, setBeautificationInfo] = useState<{
    total_pages: number;
    pages_processed: number;
    pages_with_warnings: number;
    current_page: number;
  } | null>(null);
  const [isBeautifying, setIsBeautifying] = useState(false);
  const [beautifyProgress, setBeautifyProgress] = useState<string>('');
  const [visualPreviewUrl, setVisualPreviewUrl] = useState<string | null>(null);
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
    if (!overview?.document.id || isBeautifying) return;
    
    setIsBeautifying(true);
    setVisualPreviewUrl(null);
    setBeautifiedContent(null);
    setBeautifyProgress('Starting beautification...');
    setBeautificationInfo(null);
    setShowNotes(true); // Show notes viewer immediately
    
    try {
      // Use streaming for real-time progress
      // EventSource doesn't use proxy, so we need to construct the full backend URL
      const backendUrl = window.location.hostname === 'localhost' 
        ? 'http://localhost:8000' 
        : '';
      const eventSource = new EventSource(
        `${backendUrl}/api/v1/notes/${overview.document.id}/beautify-visual/stream`
      );
      
      let totalPages = 0;
      let successfulPages = 0;
      let failedPages = 0;
      let htmlParts: string[] = [];
      let cssTemplate = '';

      const updateLivePreview = () => {
        // Close tags temporarily for rendering
        const currentHtml = htmlParts.join('\n') + `
            </main>
            <script>
                // Auto-scroll to bottom to show new content
                window.scrollTo(0, document.body.scrollHeight);
                
                // Render math
                if (window.renderMathInElement) {
                    renderMathInElement(document.body, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false},
                            {left: '\\\\[', right: '\\\\]', display: true},
                            {left: '\\\\(', right: '\\\\)', display: false}
                        ],
                        throwOnError: false
                    });
                }
            </script>
        </body>
        </html>`;
        
        const blob = new Blob([currentHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        setVisualPreviewUrl(url);
      };
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'start') {
            totalPages = data.total_pages;
            cssTemplate = data.css || '';
            
            // Initialize HTML structure
            htmlParts = [`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Preview</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>${cssTemplate}</style>
</head>
<body>
    <div class="document-container">
        <header class="document-header">
            <h1 class="document-title">📚 Live Preview</h1>
            <p class="document-subtitle">Beautifying your notes in real-time...</p>
            <div class="document-meta">Processing...</div>
        </header>
        <main>`];
            
            updateLivePreview();
            
            setBeautifyProgress(`Processing ${totalPages} pages...`);
            setBeautificationInfo({
              total_pages: totalPages,
              pages_processed: 0,
              pages_with_warnings: 0,
              current_page: 0
            });
          } else if (data.type === 'progress') {
            setBeautifyProgress(`Processing page ${data.page} of ${data.total}...`);
            setBeautificationInfo(prev => prev ? {
              ...prev,
              current_page: data.page
            } : null);
          } else if (data.type === 'page_done') {
            if (data.success) {
              successfulPages++;
              // Append page HTML
              const pageHtml = `<section class="page-section" id="page-${data.page}">
                <div class="page-header">
                    <span class="page-number">${data.page}</span>
                    <h2 class="page-title">Page ${data.page}</h2>
                </div>
                <div class="page-content">${data.html}</div>
            </section>`;
              htmlParts.push(pageHtml);
              updateLivePreview();
            } else {
              failedPages++;
            }
            setBeautificationInfo(prev => prev ? {
              ...prev,
              pages_processed: successfulPages + failedPages,
              pages_with_warnings: failedPages
            } : null);
            setBeautifyProgress(`Completed page ${data.page} of ${data.total}`);
          } else if (data.type === 'complete') {
            eventSource.close();
            // Switch to the final server-generated URL which has the TOC and everything perfect
            // Use full backend URL to ensure it works across different ports
            const previewUrl = `${backendUrl}${api.getVisualPreviewUrl(overview.document.id)}`;
            setVisualPreviewUrl(previewUrl);
            setBeautificationInfo({
              total_pages: data.total_pages,
              pages_processed: data.successful,
              pages_with_warnings: data.total_pages - data.successful,
              current_page: data.total_pages
            });
            setBeautifyProgress('');
            setIsBeautifying(false);
          } else if (data.type === 'error') {
            eventSource.close();
            setBeautifyProgress('');
            setIsBeautifying(false);
            alert('Beautification failed: ' + data.message);
          }
        } catch (e) {
          console.error('Error parsing SSE event:', e);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        setBeautifyProgress('');
        setIsBeautifying(false);
        alert('Connection lost during beautification. Please try again.');
      };
    } catch (error: any) {
      console.error('Note beautification error:', error);
      alert('Failed to beautify notes: ' + (error.response?.data?.detail || error.message));
      setIsBeautifying(false);
      setBeautifyProgress('');
    }
  };

  const handleDownloadNotes = async () => {
    if (!overview?.document.id) return;
    
    try {
      const blob = await api.downloadVisualBeautifiedNotes(overview.document.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${overview.document.filename}_beautified.html`;
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
                <h3 style={{ marginTop: '30px' }}>📝 Note Beautification</h3>
                
                <button 
                  className="rewrite-btn"
                  onClick={handleRewriteNotes}
                  disabled={isBeautifying}
                  style={{ width: '100%', marginBottom: '8px' }}
                >
                  {isBeautifying ? '✨ Beautifying...' : '✨ Beautify My Notes'}
                </button>
                
                {beautifyProgress && (
                  <p style={{ fontSize: '0.85rem', color: '#6366f1', margin: '8px 0' }}>
                    {beautifyProgress}
                  </p>
                )}
                
                {beautificationInfo && isBeautifying && (
                  <div style={{ 
                    background: '#f3f4f6', 
                    borderRadius: '8px', 
                    padding: '8px', 
                    marginBottom: '8px'
                  }}>
                    <div style={{ 
                      height: '6px', 
                      background: '#e5e7eb', 
                      borderRadius: '3px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${(beautificationInfo.pages_processed / beautificationInfo.total_pages) * 100}%`,
                        background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                    <p style={{ fontSize: '0.75rem', margin: '4px 0 0', color: '#666' }}>
                      {beautificationInfo.pages_processed}/{beautificationInfo.total_pages} pages
                    </p>
                  </div>
                )}
                
                {visualPreviewUrl && (
                  <button 
                    className="download-btn"
                    onClick={handleDownloadNotes}
                    style={{ width: '100%' }}
                  >
                    ⬇️ Download HTML
                  </button>
                )}
              </div>
            </aside>

            {showNotes && visualPreviewUrl ? (
              <div className="notes-viewer">
                <div className="notes-header">
                  <h2>📝 Beautified Notes</h2>
                  {beautificationInfo && (
                    <span className="note-stats">
                      {beautificationInfo.pages_processed}/{beautificationInfo.total_pages} pages • 
                      {beautificationInfo.pages_with_warnings > 0 ? ` ⚠️ ${beautificationInfo.pages_with_warnings} with warnings` : ' ✓ All pages processed'}
                    </span>
                  )}
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <a 
                      href={visualPreviewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="open-new-tab-btn"
                      style={{
                        padding: '6px 12px',
                        background: '#4f46e5',
                        color: 'white',
                        borderRadius: '6px',
                        textDecoration: 'none',
                        fontSize: '0.9rem'
                      }}
                    >
                      Open in New Tab ↗
                    </a>
                    <button 
                      className="close-notes-btn"
                      onClick={() => setShowNotes(false)}
                    >
                      ← Back to Chat
                    </button>
                  </div>
                </div>
                <div className="notes-content" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <iframe 
                    src={visualPreviewUrl}
                    style={{
                      width: '100%',
                      flex: 1,
                      border: 'none',
                      borderRadius: '8px',
                      background: 'white',
                      minHeight: '600px'
                    }}
                    title="Beautified Notes Preview"
                  />
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
