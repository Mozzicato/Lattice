import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import './Modal.css';
import { api, Message, Session, Document as ApiDocument } from './api';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [doc, setDoc] = useState<ApiDocument | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [beautifiedContent, setBeautifiedContent] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleStartSession = async () => {
    try {
      const newSession = await api.createSession(doc?.id);
      setSession(newSession);
    } catch (error) {
      console.error(error);
      alert("Failed to start session");
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setIsLoading(true);
      try {
        const newDoc = await api.uploadDocument(event.target.files[0]);
        setDoc(newDoc);
        // Auto-start session on upload for MVP flow
        const newSession = await api.createSession(newDoc.id);
        setSession(newSession);
      } catch (error: any) {
        console.error("Upload error details:", error);
        alert(`Upload failed: ${error.message || "Unknown error"}`);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || !session) return;

    const tempInput = input;
    setInput("");
    
    // Optimistic update (optional, but good for UX)
    // For now, we wait for server response to keep state simple

    try {
      setIsLoading(true);
      await api.sendMessage(session.id, tempInput);
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
      await api.generateMentalModel(session.id);
      const updatedMessages = await api.getMessages(session.id);
      setMessages(updatedMessages);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleBeautify = async () => {
      if (!doc) return;
      try {
          setIsLoading(true);
          const updatedDoc = await api.beautifyDocument(doc.id);
          if (updatedDoc.pages && updatedDoc.pages.length > 0 && updatedDoc.pages[0].beautified_text) {
              setBeautifiedContent(updatedDoc.pages[0].beautified_text);
          } else {
              alert("Beautification complete, but no content returned.");
          }
      } catch (error: any) {
          console.error(error);
          alert("Failed to beautify document");
      } finally {
          setIsLoading(false);
      }
  };

  const handleDownload = () => {
      if (!beautifiedContent) return;
      const element = document.createElement("a");
      const file = new Blob([beautifiedContent], {type: 'text/markdown'});
      element.href = URL.createObjectURL(file);
      element.download = "beautified_notes.md";
      document.body.appendChild(element); // Required for this to work in FireFox
      element.click();
      document.body.removeChild(element);
  };

  return (
    <div className="app-container">
      {beautifiedContent && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>✨ Beautified Notes</h2>
            <div className="markdown-preview">
              <pre>{beautifiedContent}</pre>
            </div>
            <div className="modal-actions">
              <button onClick={handleDownload} className="download-btn">📥 Download Markdown</button>
              <button onClick={() => setBeautifiedContent(null)} className="close-btn">Close</button>
            </div>
          </div>
        </div>
      )}
      <aside className="sidebar">
        <h1>Lattice</h1>
        <div className="upload-section">
          <h3>Document</h3>
          <input type="file" onChange={handleFileUpload} disabled={isLoading} />
          {doc && (
            <div className="doc-info">
              <p>📄 {doc.filename}</p>
              <button onClick={handleBeautify} disabled={isLoading}>✨ Beautify Notes</button>
            </div>
          )}
        </div>
        
        {session && (
            <div className="tools-section">
                <h3>Tools</h3>
                <button className="tool-btn mental-model" onClick={handleMentalModel} disabled={isLoading}>
                    🧠 Build Mental Model
                </button>
            </div>
        )}
      </aside>

      <main className="chat-area">
        {!session ? (
          <div className="welcome-screen">
            <h2>Welcome to Lattice</h2>
            <p>Upload a document or start a session to begin learning.</p>
            <button onClick={handleStartSession} disabled={isLoading}>Start Empty Session</button>
          </div>
        ) : (
          <>
            <div className="messages-list">
              {messages.map((msg) => (
                <div key={msg.id} className={`message ${msg.role}`}>
                  <div className="message-content">
                    {msg.content}
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
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your question..."
                  disabled={isLoading}
                />
                <button type="submit" disabled={isLoading || !input.trim()}>Send</button>
              </form>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
