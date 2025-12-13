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
      timeout: 30000  // 30 second timeout for upload
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

  // Notes - Beautification
  async beautifyNotes(documentId: string, targetLanguageLevel: string = "undergraduate"): Promise<{
    document_id: string;
    original_filename: string;
    beautification_status: string;
    total_pages: number;
    pages_processed: number;
    pages_with_warnings: number;
    beautified_pages: Array<{
      page_number: number;
      original_text_length: number;
      beautified_text: string;
      beautified_text_length: number;
      estimated_confidence: number;
      formula_count: number;
      low_confidence_warnings: string[];
    }>;
    document_title: string;
    introduction: string;
    conclusion: string;
    low_confidence_summary?: string;
    download_url: string;
  }> {
    const response = await this.client.post('/notes/beautify', {
      document_id: documentId,
      target_language_level: targetLanguageLevel,
      include_image_references: true
    });
    return response.data;
  }

  async downloadBeautifiedNotes(documentId: string): Promise<Blob> {
    const response = await this.client.get(`/notes/${documentId}/beautified/download`, {
      responseType: 'blob',
    });
    return response.data;
  }

  // Visual Beautification - generates beautiful HTML/CSS output
  async beautifyNotesVisual(documentId: string): Promise<{
    document_id: string;
    original_filename: string;
    status: string;
    total_pages: number;
    pages_analyzed: number;
    successful_analyses: number;
    html_preview_url: string;
    html_download_url: string;
    created_at: string;
    page_results: Array<{
      page_number: number;
      success: boolean;
      error?: string;
    }>;
  }> {
    const response = await this.client.post('/notes/beautify-visual', {
      document_id: documentId
    });
    return response.data;
  }

  getVisualPreviewUrl(documentId: string): string {
    return `${API_BASE_URL}/notes/${documentId}/beautified-visual/preview`;
  }

  getBaseUrl(): string {
    return API_BASE_URL.startsWith('/') ? '' : API_BASE_URL;
  }

  async downloadVisualBeautifiedNotes(documentId: string): Promise<Blob> {
    const response = await this.client.get(`/notes/${documentId}/beautified-visual/download`, {
      responseType: 'blob',
    });
    return response.data;
  }
}

export const api = new ApiClient();
