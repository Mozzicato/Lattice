import React, { useState, useEffect, useRef } from 'react';
import './App.css';
// @ts-ignore
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import { api, Message, Session, Document as ApiDocument, Page } from './api';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [doc, setDoc] = useState<ApiDocument | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [beautifiedContent, setBeautifiedContent] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pdfContainerRef = useRef<HTMLDivElement>(null);

  // Edit modal state
  const [editingPage, setEditingPage] = useState<Page | null>(null);
  const [editLatex, setEditLatex] = useState("");
  const [editOcr, setEditOcr] = useState("");

  // View mode: 'styled' (dark/current) or 'pdf' (white background like a real PDF)
  const [viewMode, setViewMode] = useState<'styled' | 'pdf'>('styled');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Render LaTeX content with proper delimiters
  const renderLatexContent = (content: string) => {
    const parts = content.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)/g);

    return parts.map((part, index) => {
      if (part.startsWith('$$') && part.endsWith('$$')) {
        const latex = part.slice(2, -2).trim();
        try {
          return <BlockMath key={index} math={latex} />;
        } catch {
          return <pre key={index} style={{ color: '#ef4444' }}>{part}</pre>;
        }
      } else if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        const latex = part.slice(1, -1).trim();
        try {
          return <InlineMath key={index} math={latex} />;
        } catch {
          return <code key={index}>{part}</code>;
        }
      } else {
        // Parse markdown-like formatting
        return <span key={index} dangerouslySetInnerHTML={{ __html: formatText(part) }} />;
      }
    });
  };

  // Simple markdown formatter
  const formatText = (text: string): string => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br/>');
  };

  const handleStartSession = async () => {
    try {
      setIsLoading(true);
      setLoadingMessage("Starting session...");
      const newSession = await api.createSession(doc?.id);
      setSession(newSession);
    } catch (error) {
      console.error(error);
      alert("Failed to start session");
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    setLoadingMessage(`Uploading ${file.name}...`);

    try {
      const newDoc = await api.uploadDocument(file);
      setDoc(newDoc);
      
      // Auto-start session
      setLoadingMessage("Starting session...");
      const newSession = await api.createSession(newDoc.id);
      setSession(newSession);
    } catch (error: any) {
      console.error("Upload error:", error);
      alert(`Upload failed: ${error.message || "Unknown error"}`);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const handleBeautify = async () => {
    if (!doc) return;
    setIsLoading(true);
    setLoadingMessage("✨ Submitting beautify job...");

    try {
      // Kick off background beautify and get immediate doc state
      const updatedDoc = await api.beautifyDocument(doc.id);
      setDoc(updatedDoc);

      // Show combined text from all pages with page headers
      const pages = updatedDoc.pages
        ?.filter((p: any) => p.beautified_text)
        .sort((a: any, b: any) => a.page_number - b.page_number);

      if (pages && pages.length > 0) {
        const combined = pages
          .map((p: any) => `## Page ${p.page_number}\n\n${p.beautified_text}`)
          .join("\n\n---\n\n");
        setBeautifiedContent(combined);
        setLoadingMessage("");
        setIsLoading(false);
        return;
      }

      // Poll job for real-time progress
      const jobId = (updatedDoc as any).job_id;
      if (!jobId) {
        alert("No job ID returned");
        setIsLoading(false);
        return;
      }

      setLoadingMessage("📄 Processing pages...");
      const start = Date.now();
      const timeoutMs = 300000; // 5 minutes

      while (Date.now() - start < timeoutMs) {
        await new Promise((r) => setTimeout(r, 1500));
        
        // Poll job for progress message
        const jobResp = await fetch(`/api/v1/documents/jobs/${jobId}`);
        if (jobResp.ok) {
          const jobData = await jobResp.json();
          setLoadingMessage(`📄 ${jobData.message || "Processing..."}`);
          
          if (jobData.status === 'completed') {
            // Job done, fetch document to get all beautified content
            const docResp = await fetch(`/api/v1/documents/${doc.id}`);
            if (docResp.ok) {
              const finalDoc = await docResp.json();
              setDoc(finalDoc);
              
              const allText = finalDoc.pages
                ?.filter((p: any) => p.beautified_text)
                .sort((a: any, b: any) => a.page_number - b.page_number)
                .map((p: any) => `## Page ${p.page_number}\n\n${p.beautified_text}`)
                .join("\n\n---\n\n");
              
              if (allText) {
                setBeautifiedContent(allText);
              }
            }
            setLoadingMessage("");
            setIsLoading(false);
            return;
          }
        }
      }

      // Timeout reached
      alert('Beautify is still running — it may take longer. Check back later.');

    } catch (error: any) {
      console.error(error);
      alert(`Beautification failed: ${error.message || "Unknown error"}`);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const handleProcess = async () => {
    if (!doc) return;

    setIsLoading(true);
    setLoadingMessage("🔍 Running OCR and extracting equations...");

    try {
      const result = await api.processDocument(doc.id);
      
      // Refresh doc to get updated pages
      const resp = await fetch(`/api/v1/documents/${doc.id}`);
      const updatedDoc = await resp.json();
      setDoc(updatedDoc);

      if (result.ocr_text) {
        alert(`OCR Complete!\n\nExtracted ${result.ocr_text.length} characters.\nFound ${result.equations_found || 0} equations.`);
      }
    } catch (error: any) {
      console.error(error);
      alert(`Processing failed: ${error.message || "Unknown error"}`);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || !session) return;

    const userMessage = input;
    setInput("");

    try {
      setIsLoading(true);
      await api.sendMessage(session.id, userMessage);
      const updatedMessages = await api.getMessages(session.id);
      setMessages(updatedMessages);
    } catch (error) {
      console.error(error);
      alert("Failed to send message");
    } finally {
      setIsLoading(false);
    }
  };

  const handleImLost = async () => {
    if (!session) return;
    try {
      setIsLoading(true);
      await api.explainDifferently(session.id);
      const updatedMessages = await api.getMessages(session.id);
      setMessages(updatedMessages);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMentalModel = async () => {
    if (!session) return;
    try {
      setIsLoading(true);
      setLoadingMessage("🧠 Building mental model...");
      await api.generateMentalModel(session.id);
      const updatedMessages = await api.getMessages(session.id);
      setMessages(updatedMessages);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const handleDownload = () => {
    if (!beautifiedContent) return;
    const blob = new Blob([beautifiedContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${doc?.filename || 'notes'}_beautified.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadPDF = async () => {
    if (!beautifiedContent) return;
    
    setIsLoading(true);
    setLoadingMessage("📥 Preparing PDF pages...");
    
    try {
      // We must be in PDF view so the white pages are rendered in the DOM
      const prevMode = viewMode;
      if (viewMode !== 'pdf') {
        setViewMode('pdf');
        // Wait for React to render the PDF pages
        await new Promise(r => setTimeout(r, 800));
      }

      // Wait one more tick for KaTeX to finish rendering
      await new Promise(r => setTimeout(r, 300));

      const container = pdfContainerRef.current;
      if (!container) {
        throw new Error("Could not find rendered pages. Try switching to PDF View manually first.");
      }

      const pages = container.querySelectorAll('.pdf-page') as NodeListOf<HTMLElement>;
      if (pages.length === 0) {
        throw new Error("No pages found to export");
      }

      setLoadingMessage(`📥 Capturing ${pages.length} page(s)...`);

      // Use jsPDF directly so we can capture each page individually
      const { default: jsPDF } = await import('jspdf');
      const { default: html2canvas } = await import('html2canvas');

      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'pt',
        format: 'letter', // 612 x 792 pt
      });

      const pdfWidth = 612;
      const pdfHeight = 792;

      for (let i = 0; i < pages.length; i++) {
        setLoadingMessage(`📥 Rendering page ${i + 1} of ${pages.length}...`);

        const page = pages[i];

        // Capture the visible DOM element directly (no off-screen cloning)
        const canvas = await html2canvas(page, {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          logging: false,
          // Ensure we capture the element as it looks on screen
          scrollX: 0,
          scrollY: 0,
          windowWidth: page.scrollWidth,
          windowHeight: page.scrollHeight,
        });

        const imgData = canvas.toDataURL('image/jpeg', 0.95);

        // Calculate dimensions to fit the page proportionally
        const canvasRatio = canvas.width / canvas.height;
        const pageRatio = pdfWidth / pdfHeight;

        let imgW = pdfWidth;
        let imgH = pdfWidth / canvasRatio;

        // If the image is taller than the page, scale down to fit height
        if (imgH > pdfHeight) {
          imgH = pdfHeight;
          imgW = pdfHeight * canvasRatio;
        }

        if (i > 0) {
          pdf.addPage();
        }

        // Center the image on the page
        const xOffset = (pdfWidth - imgW) / 2;
        const yOffset = 0;
        pdf.addImage(imgData, 'JPEG', xOffset, yOffset, imgW, imgH);
      }

      pdf.save(`beautified_${doc?.filename || 'notes'}.pdf`);

      // Restore view mode if we changed it
      if (prevMode !== 'pdf') {
        setViewMode(prevMode);
      }
      setLoadingMessage("");
    } catch (error: any) {
      console.error(error);
      alert(`PDF download failed: ${error.message}`);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  };

  const openEditPage = (page: Page) => {
    setEditingPage(page);
    setEditLatex(page.latex_content || "");
    setEditOcr(page.ocr_text || "");
  };

  const closeEdit = () => {
    setEditingPage(null);
    setEditLatex("");
    setEditOcr("");
  };

  const saveEdit = async () => {
    if (!editingPage || !doc) return;
    
    try {
      setIsLoading(true);
      await api.updatePage(doc.id, editingPage.id, { 
        latex_content: editLatex, 
        ocr_text: editOcr 
      });
      
      // Refresh doc
      const resp = await fetch(`/api/v1/documents/${doc.id}`);
      const updatedDoc = await resp.json();
      setDoc(updatedDoc);
      closeEdit();
    } catch (error: any) {
      alert(`Failed to save: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Loading Overlay */}
      {isLoading && loadingMessage && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="spinner-large" />
            <p>{loadingMessage}</p>
          </div>
        </div>
      )}

      {/* Beautified Notes Modal */}
      {beautifiedContent && (
        <div className="modal-overlay" onClick={() => setBeautifiedContent(null)}>
          <div className={`modal-content ${viewMode === 'pdf' ? 'modal-content-pdf' : ''}`} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>✨ Beautified Notes</h2>
              <div className="view-toggle">
                <button
                  className={`toggle-btn ${viewMode === 'styled' ? 'active' : ''}`}
                  onClick={() => setViewMode('styled')}
                  title="Styled view"
                >
                  🎨 Styled
                </button>
                <button
                  className={`toggle-btn ${viewMode === 'pdf' ? 'active' : ''}`}
                  onClick={() => setViewMode('pdf')}
                  title="PDF-like view"
                >
                  📄 PDF View
                </button>
              </div>
              <button className="close-btn-x" onClick={() => setBeautifiedContent(null)}>×</button>
            </div>
            <div className={`modal-body ${viewMode === 'pdf' ? 'modal-body-pdf' : ''}`}>
              {viewMode === 'styled' ? (
                <div className="beautified-preview">
                  {renderLatexContent(beautifiedContent)}
                </div>
              ) : (
                <div className="pdf-scroll-container" ref={pdfContainerRef}>
                  {beautifiedContent.split('\n\n---\n\n').map((pageContent, idx) => (
                    <div key={idx} className="pdf-page">
                      <div className="pdf-page-content">
                        {renderLatexContent(pageContent)}
                      </div>
                      <div className="pdf-page-number">Page {idx + 1}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setBeautifiedContent(null)}>Close</button>
              <button className="btn btn-primary" onClick={handleDownload}>📥 Download Markdown</button>
              <button className="btn btn-primary" onClick={handleDownloadPDF} disabled={isLoading}>📕 Download PDF</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Page Modal */}
      {editingPage && (
        <div className="modal-overlay" onClick={closeEdit}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Edit Page {editingPage.page_number}</h2>
              <button className="close-btn-x" onClick={closeEdit}>×</button>
            </div>
            <div className="modal-body">
              <div className="edit-grid">
                <div className="edit-section">
                  <h4>OCR Text</h4>
                  <textarea 
                    value={editOcr} 
                    onChange={e => setEditOcr(e.target.value)}
                    placeholder="Raw OCR text..."
                  />
                </div>
                <div className="edit-section">
                  <h4>LaTeX / Math Content</h4>
                  <textarea 
                    value={editLatex} 
                    onChange={e => setEditLatex(e.target.value)}
                    placeholder="LaTeX equations..."
                  />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={closeEdit}>Cancel</button>
              <button className="btn btn-primary" onClick={saveEdit} disabled={isLoading}>
                {isLoading ? <><span className="loading-spinner" />Saving...</> : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Lattice</h1>
        </div>
        
        <div className="sidebar-content">
          {/* Upload Section */}
          <div className="upload-section">
            <div className="section-title">Upload Document</div>
            <div className="upload-zone">
              <div className="upload-icon">📄</div>
              <p>Drop your notes here or click to browse</p>
              <span className="supported-formats">PDF, PNG, JPG, JPEG supported</span>
              <input 
                type="file" 
                accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
                onChange={handleFileUpload}
                disabled={isLoading}
              />
            </div>

            {/* Document Card */}
            {doc && (
              <div className="document-card">
                <div className="document-card-header">
                  <div className="file-icon">📝</div>
                  <div className="file-info">
                    <div className="file-name">{doc.filename}</div>
                    <div className="file-status">
                      <span className={`status-dot ${doc.status}`} />
                      {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                    </div>
                  </div>
                </div>
                
                <div className="action-buttons">
                  <button 
                    className="btn btn-primary" 
                    onClick={handleBeautify}
                    disabled={isLoading}
                  >
                    ✨ Beautify
                  </button>
                </div>

                {/* Pages */}
                {doc.pages && doc.pages.length > 0 && (
                  <div className="pages-section">
                    <div className="section-title">Pages</div>
                    {doc.pages.map(page => (
                      <div key={page.id} className="page-item">
                        <div className="page-item-header">
                          <h4>Page {page.page_number}</h4>
                          <button 
                            className="btn btn-secondary" 
                            style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                            onClick={() => openEditPage(page)}
                          >
                            Edit
                          </button>
                        </div>
                        {(page.ocr_text || page.latex_content) && (
                          <div className="page-content-preview">
                            {page.ocr_text?.slice(0, 100) || page.latex_content?.slice(0, 100)}...
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Tools Section */}
          {session && (
            <div className="tools-section">
              <div className="section-title">AI Tools</div>
              <button 
                className="btn tool-btn" 
                onClick={handleMentalModel}
                disabled={isLoading}
              >
                🧠 Build Mental Model
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-area">
        {!session ? (
          <div className="welcome-screen">
            <h2>Welcome to Lattice</h2>
            <p>Your AI-powered study companion that transforms messy notes into beautiful, structured knowledge.</p>
            <button className="btn btn-primary" onClick={handleStartSession} disabled={isLoading}>
              {isLoading ? <><span className="loading-spinner" />Starting...</> : 'Start Learning Session'}
            </button>
            
            <div className="feature-cards">
              <div className="feature-card">
                <div className="icon">📝</div>
                <h3>Smart OCR</h3>
                <p>Extract text from handwritten notes and images with AI-powered OCR.</p>
              </div>
              <div className="feature-card">
                <div className="icon">✨</div>
                <h3>Note Beautification</h3>
                <p>Transform messy notes into clean, formatted documents with LaTeX math.</p>
              </div>
              <div className="feature-card">
                <div className="icon">🧠</div>
                <h3>Mental Models</h3>
                <p>Build understanding with AI-generated explanations and visualizations.</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="messages-list">
              {messages.length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '40px' }}>
                  <p>No messages yet. Ask a question about your notes!</p>
                </div>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={`message ${msg.role}`}>
                  <div className="message-content">
                    {renderLatexContent(msg.content)}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="input-area">
              <button 
                className="im-lost-btn" 
                onClick={handleImLost}
                disabled={isLoading}
              >
                🆘 I'm Lost
              </button>
              <form onSubmit={handleSendMessage} className="message-form">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Ask about your notes..."
                  disabled={isLoading}
                />
                <button type="submit" disabled={isLoading || !input.trim()}>
                  Send
                </button>
              </form>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
