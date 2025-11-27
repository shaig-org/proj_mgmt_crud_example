import axios, { AxiosInstance } from 'axios';

// Use E2E port during E2E testing, dev port otherwise
const API_BASE_URL = import.meta.env.VITE_E2E_TESTING === 'true'
  ? 'http://localhost:18000'
  : 'http://localhost:8000';

interface HealthResponse {
  status: string;
}

interface LoginRequest {
  username: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  organization_id: string | null;
  role: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Epic {
  id: string;
  name: string;
  description: string | null;
  organization_id: string;
  created_at: string;
  updated_at: string;
}

export enum TicketPriority {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

export interface Ticket {
  id: string;
  title: string;
  description: string | null;
  priority: TicketPriority | null;
  status: string;
  assignee_id: string | null;
  reporter_id: string;
  project_id: string;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: string;
  ticket_id: string;
  author_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface UserCreateResponse {
  user: User;
  generated_password: string;
}

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor(baseURL: string = API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });
  }

  setToken(token: string | null) {
    this.token = token;
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.client.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  }

  async getProjects(): Promise<Project[]> {
    const response = await this.client.get<Project[]>('/api/projects');
    return response.data;
  }

  async getProject(projectId: string): Promise<Project> {
    const response = await this.client.get<Project>(`/api/projects/${projectId}`);
    return response.data;
  }

  async createProject(data: { name: string; description?: string }): Promise<Project> {
    const response = await this.client.post<Project>('/api/projects', data);
    return response.data;
  }

  async getUsers(): Promise<User[]> {
    const response = await this.client.get<User[]>('/api/users');
    return response.data;
  }

  async createUser(data: {
    username: string;
    email: string;
    full_name: string;
    organization_id: string;
    role: string;
  }): Promise<UserCreateResponse> {
    const response = await this.client.post<UserCreateResponse>('/api/users', {
      username: data.username,
      email: data.email,
      full_name: data.full_name,
    }, {
      params: {
        organization_id: data.organization_id,
        role: data.role,
      },
    });
    return response.data;
  }

  async getOrganizations(): Promise<Organization[]> {
    const response = await this.client.get<Organization[]>('/api/organizations');
    return response.data;
  }

  async createOrganization(data: { name: string; description?: string }): Promise<Organization> {
    const response = await this.client.post<Organization>('/api/organizations', data);
    return response.data;
  }

  async getEpics(projectId?: string): Promise<Epic[]> {
    const params = projectId ? { project_id: projectId } : undefined;
    const response = await this.client.get<Epic[]>('/api/epics', { params });
    return response.data;
  }

  async getEpic(epicId: string): Promise<Epic> {
    const response = await this.client.get<Epic>(`/api/epics/${epicId}`);
    return response.data;
  }

  async createEpic(data: { name: string; description?: string }): Promise<Epic> {
    const response = await this.client.post<Epic>('/api/epics', data);
    return response.data;
  }

  async addTicketToEpic(epicId: string, ticketId: string): Promise<void> {
    await this.client.post(`/api/epics/${epicId}/tickets`, null, {
      params: { ticket_id: ticketId },
    });
  }

  async removeTicketFromEpic(epicId: string, ticketId: string): Promise<void> {
    await this.client.delete(`/api/epics/${epicId}/tickets/${ticketId}`);
  }

  async getEpicTickets(epicId: string): Promise<Ticket[]> {
    const response = await this.client.get<Ticket[]>(`/api/epics/${epicId}/tickets`);
    return response.data;
  }

  async getTickets(projectId?: string, status?: string, assigneeId?: string): Promise<Ticket[]> {
    const params: Record<string, string> = {};
    if (projectId) params.project_id = projectId;
    if (status) params.status = status;
    if (assigneeId) params.assignee_id = assigneeId;

    const response = await this.client.get<Ticket[]>('/api/tickets', {
      params: Object.keys(params).length > 0 ? params : undefined
    });
    return response.data;
  }

  async getTicket(ticketId: string): Promise<Ticket> {
    const response = await this.client.get<Ticket>(`/api/tickets/${ticketId}`);
    return response.data;
  }

  async createTicket(data: {
    title: string;
    description?: string;
    priority?: TicketPriority;
    projectId: string;
    assigneeId?: string;
  }): Promise<Ticket> {
    const params: Record<string, string> = { project_id: data.projectId };
    if (data.assigneeId) params.assignee_id = data.assigneeId;

    const response = await this.client.post<Ticket>(
      '/api/tickets',
      {
        title: data.title,
        description: data.description || undefined,
        priority: data.priority || undefined,
      },
      { params }
    );
    return response.data;
  }

  async updateTicketStatus(ticketId: string, status: string): Promise<Ticket> {
    const response = await this.client.put<Ticket>(`/api/tickets/${ticketId}/status`, { status });
    return response.data;
  }

  async updateTicketAssignee(ticketId: string, assigneeId: string | null): Promise<Ticket> {
    const response = await this.client.put<Ticket>(`/api/tickets/${ticketId}/assignee`, {
      assignee_id: assigneeId,
    });
    return response.data;
  }

  // Comment endpoints
  async getComments(ticketId: string): Promise<Comment[]> {
    const response = await this.client.get<Comment[]>(`/api/tickets/${ticketId}/comments`);
    return response.data;
  }

  async createComment(ticketId: string, content: string): Promise<Comment> {
    const response = await this.client.post<Comment>(`/api/tickets/${ticketId}/comments`, {
      content,
    });
    return response.data;
  }

  async deleteComment(commentId: string): Promise<void> {
    await this.client.delete(`/api/comments/${commentId}`);
  }
}

export const apiClient = new ApiClient();
export default apiClient;
