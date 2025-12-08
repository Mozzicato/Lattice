import axios from 'axios';

const API_BASE_URL = '/api/v1';

export interface Document {
  id: string;
  filename: string;
  raw_text?: string;
  doc_metadata?: {
    equation_count: number;
    character_count: number;
    status: string;
    concepts?: Array<{ term: string; definition: string }>;
    sections?: Array<{ level: number; title: string; line: number }>;
    processing_complete?: boolean;
  };
  created_at: string;
  equations?: Equation[];
}

export interface Equation {
  id: string;
  latex: string;
  context?: string;
  section_title?: string;
  position: number;
}

export interface Session {
  session_id: string;
  document_id: string;
  status: string;
  current_step: string;
  progress: {
    equations_total: number;
    equations_studied: number;
    concepts_total: number;
    concepts_covered: number;
  };
}

export interface SessionOverview {
  document: {
    id: string;
    filename: string;
    character_count: number;
  };
  concepts: Array<{ term: string; definition: string }>;
  sections: Array<{ level: number; title: string; line: number }>;
  equations: Array<{
    id: string;
    latex: string;
    section: string;
    position: number;
  }>;
  ready_for_learning: boolean;
}

export interface QuestionResponse {
  answer: string;
  related_equations: string[];
  references: string[];
}

class ApiClient {
  private client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Documents
  async uploadDocument(file: File): Promise<{ document_id: string; status: string; poll_url: string }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getDocument(documentId: string): Promise<Document> {
    const response = await this.client.get(`/documents/${documentId}`);
    return response.data;
  }

  // Sessions
  async startSession(documentId: string, learningGoals?: string[]): Promise<Session> {
    const response = await this.client.post('/sessions/start', {
      document_id: documentId,
      learning_goals: learningGoals,
    });
    return response.data;
  }

  async getSessionOverview(sessionId: string): Promise<SessionOverview> {
    const response = await this.client.get(`/sessions/${sessionId}/overview`);
    return response.data;
  }

  async askQuestion(sessionId: string, question: string): Promise<QuestionResponse> {
    const response = await this.client.post(`/sessions/${sessionId}/ask`, {
      question,
    });
    return response.data;
  }

  async completeSession(sessionId: string): Promise<any> {
    const response = await this.client.post(`/sessions/${sessionId}/complete`);
    return response.data;
  }

  // Notes
  async rewriteNotes(documentId: string): Promise<{
    title: string;
    formatted_content: string;
    sections: Array<{ title: string; content: string[] }>;
    page_count: number;
    image_count: number;
    download_url: string;
  }> {
    const response = await this.client.post('/notes/rewrite', {
      document_id: documentId,
    });
    return response.data;
  }

  async downloadNotes(documentId: string): Promise<Blob> {
    const response = await this.client.get(`/notes/${documentId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  }
}

export const api = new ApiClient();
