const API_URL = "/api/v1";

export interface Message {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  message_type: "text" | "audio" | "image" | "command" | "audio_transcription";
  timestamp: string;
}

export interface Session {
  id: number;
  title: string | null;
  created_at: string;
}

export interface Page {
  id: number;
  page_number: number;
  ocr_text?: string | null;
  latex_content?: string | null;
  beautified_text: string | null;
}

export interface Document {
  id: number;
  filename: string;
  status: string;
  upload_date: string;
  pages: Page[];
}

export const api = {
  // Documents
  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_URL}/documents/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Upload failed: ${response.status}`);
    }
    return response.json();
  },

  // Sessions
  createSession: async (documentId?: number): Promise<Session> => {
    const response = await fetch(`${API_URL}/sessions/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New Session", document_id: documentId }),
    });
    if (!response.ok) throw new Error("Failed to create session");
    return response.json();
  },

  getMessages: async (sessionId: number): Promise<Message[]> => {
    const response = await fetch(`${API_URL}/sessions/${sessionId}/messages`);
    if (!response.ok) throw new Error("Failed to fetch messages");
    return response.json();
  },

  sendMessage: async (sessionId: number, content: string): Promise<Message> => {
    const response = await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content, message_type: "text" }),
    });
    if (!response.ok) throw new Error("Failed to send message");
    return response.json();
  },

  // Special Features
  explainDifferently: async (sessionId: number): Promise<Message> => {
    const response = await fetch(`${API_URL}/sessions/${sessionId}/explain-differently`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Failed to trigger explain differently");
    return response.json();
  },

  generateMentalModel: async (sessionId: number): Promise<Message> => {
    const response = await fetch(`${API_URL}/sessions/${sessionId}/mental-model`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Failed to generate mental model");
    return response.json();
  },
  
  beautifyDocument: async (documentId: number): Promise<Document> => {
      const response = await fetch(`${API_URL}/documents/${documentId}/beautify`, {
          method: "POST"
      });
      if (!response.ok) throw new Error("Failed to beautify document");
      return response.json();
  },

  processDocument: async (documentId: number): Promise<any> => {
      const response = await fetch(`${API_URL}/documents/${documentId}/process`, {
          method: "POST"
      });
      if (!response.ok) throw new Error("Failed to process document");
      return response.json();
  },

  updatePage: async (documentId: number, pageId: number, payload: any): Promise<any> => {
      const response = await fetch(`${API_URL}/documents/${documentId}/pages/${pageId}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Failed to update page');
      return response.json();
  }
};
