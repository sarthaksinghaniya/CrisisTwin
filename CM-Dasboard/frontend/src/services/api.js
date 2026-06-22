import axios from 'axios';

// --- Configuration ---
const API_TIMEOUT = 10000; // 10 seconds
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// --- Request Interceptor ---
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// --- Response Interceptor ---
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Auto Refresh Logic
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const res = await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true });
        const newToken = res.data.accessToken;
        
        localStorage.setItem('auth_token', newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, clear token to force logout
        localStorage.removeItem('auth_token');
        localStorage.removeItem('role');
        return Promise.reject(refreshError);
      }
    }

    if (axios.isCancel(error)) {
      return Promise.reject(new Error('Request was canceled.'));
    }

    let errorMessage = 'An unexpected error occurred. Please try again.';
    if (!error.response) {
      errorMessage = error.code === 'ECONNABORTED' 
        ? 'Request timed out. Please check your internet connection.'
        : 'Unable to connect to the server. Please check your internet connection.';
    } else {
      const data = error.response.data;
      if (error.response.status === 403) errorMessage = 'You do not have permission to perform this action.';
      else if (error.response.status >= 500) errorMessage = 'Our servers are experiencing issues. Please try later.';
      else if (data && data.detail) {
        errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    }

    return Promise.reject(new Error(errorMessage));
  }
);

// --- API Service Methods ---
// We pass config explicitly so that React Query can inject an AbortSignal

export const submitComplaint = async (data, config = {}) => {
  const response = await api.post('/complaints/', data, {
    ...config,
    headers: {
      ...config.headers,
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const trackComplaint = async (id, config = {}) => {
  const response = await api.get(`/complaints/track/${id}`, config);
  return response.data;
};

export const getOfficerComplaints = async (config = {}) => {
  const response = await api.get('/admin/complaints', config);
  return response.data;
};

export const updateComplaintStatus = async (id, status, note = null, assignedTo = null, config = {}) => {
  const response = await api.patch(`/admin/complaints/${id}`, { status, note, assigned_to: assignedTo }, config);
  return response.data;
};

export const getDashboardStats = async (config = {}) => {
  const response = await api.get('/admin/complaints', config);
  return response.data;
};

export const submitFeedback = async (data, config = {}) => {
  const response = await api.post('/feedback/', data, config);
  return response.data;
};

export default api;
