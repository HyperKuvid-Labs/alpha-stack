```typescript
import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';

/**
 * Defines the shape of the access token and token type,
 * mirroring the Token schema in backend/src/karyaksham_api/schemas/token.py.
 */
export interface Token {
  access_token: string;
  token_type: string;
}

/**
 * Defines the shape of a User object,
 * mirroring a simplified User schema from backend/src/karyaksham_api/schemas/user.py.
 */
export interface User {
  id: number;
  email: string;
  is_active: boolean;
  // Add other user-specific fields as needed (e.g., first_name, last_name, roles)
}

/**
 * Defines the shape of a Job object,
 * mirroring the Job schema from backend/src/karyaksham_api/schemas/job.py.
 */
export interface Job {
  id: string; // UUID for the job
  user_id: number;
  input_file_path: string; // S3/Object Storage path for the input file
  output_file_path?: string; // Optional S3/Object Storage path for the output file
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  created_at: string; // ISO 8601 timestamp
  updated_at: string; // ISO 8601 timestamp
  // Additional fields for job parameters or error details
  processing_parameters?: Record<string, any>; // Flexible for different job types
  error_message?: string; // Details if job status is 'FAILED'
  download_presigned_url?: string; // For direct download
  upload_presigned_url?: string; // For direct upload initiation
}

// Retrieve the API base URL from environment variables.
// In a Vite project, `import.meta.env.VITE_` is the standard prefix for client-side environment variables.
// Fallback to a default localhost URL for development if the variable is not set.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// Create a custom Axios instance to centralize API request configuration.
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // Request timeout in milliseconds (30 seconds)
});

/**
 * Request Interceptor:
 * This interceptor is executed before each request is sent.
 * It's used to attach the JWT access token to the Authorization header
 * for authenticated requests. The token is retrieved from `localStorage`.
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken'); // Get JWT from local storage

    if (token) {
      // If a token exists, set the Authorization header with a Bearer token
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    // Handle request errors (e.g., network issues before sending)
    console.error('API Request Error:', error.message);
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor:
 * This interceptor is executed for every response received from the API.
 * It's primarily used for global error handling based on HTTP status codes.
 *
 * It provides a centralized place to:
 * - Log errors.
 * - Handle specific HTTP error codes (e.g., 401 for unauthorized, 403 for forbidden).
 * - Redirect to login on token expiration/invalidity.
 * - Provide user-friendly notifications for common errors.
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // If the response is successful (status in 2xx range), simply return it.
    return response;
  },
  (error: AxiosError) => {
    // Handle API response errors
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx.
      const { status, data, config } = error.response;
      console.error(`API Error - Status: ${status}, URL: ${config.url}`, data);

      switch (status) {
        case 400:
          // Bad Request: Typically due to invalid input data.
          console.warn('Validation or Bad Request Error:', data);
          // TODO: Potentially display a user-friendly message based on 'data'
          break;
        case 401:
          // Unauthorized: JWT is missing, invalid, or expired.
          console.error('Unauthorized access. Redirecting to login...');
          localStorage.removeItem('accessToken'); // Clear invalid token
          // TODO: Implement actual redirection to login page or global logout state update.
          // Example for a React Router setup: history.push('/login');
          window.location.href = '/login'; // Simple, direct redirection
          break;
        case 403:
          // Forbidden: User authenticated but doesn't have permission.
          console.error('Forbidden access. Insufficient permissions.');
          // TODO: Display a message indicating lack of permission
          break;
        case 404:
          // Not Found: The requested resource does not exist.
          console.error('Resource Not Found.');
          break;
        case 422:
          // Unprocessable Entity: FastAPI's validation error.
          console.warn('API Validation Error (422 Unprocessable Entity):', data);
          // 'data' usually contains detailed validation errors.
          break;
        case 500:
          // Internal Server Error: Generic server-side error.
          console.error('Server Error (500 Internal Server Error). Please try again later.');
          // TODO: Display a generic error message to the user.
          break;
        default:
          // Handle any other unhandled HTTP status codes
          console.error(`Unhandled API Error: Status ${status}`, data);
          break;
      }
    } else if (error.request) {
      // The request was made but no response was received (e.g., network error, CORS issue).
      console.error('No response received from API. Network error or server unreachable.', error.request);
      // TODO: Inform the user about connectivity issues.
    } else {
      // Something happened in setting up the request that triggered an Error.
      console.error('Error setting up API request:', error.message);
    }

    // Crucially, re-throw or return a rejected promise so that
    // the calling function (`.catch()` block) can handle the error.
    return Promise.reject(error);
  }
);

/**
 * Export the configured Axios instance.
 * This `apiClient` will be imported and used by other service modules
 * (e.g., `authService.ts`, `jobService.ts`) to make API calls,
 * ensuring consistent behavior and error handling across the application.
 *
 * Example Usage in another service file:
 * ```typescript
 * import apiClient, { Job, Token } from './apiClient';
 *
 * // Example: Function to login
 * export const login = async (credentials: any): Promise<Token> => {
 *   const response = await apiClient.post<Token>('/auth/login', credentials);
 *   return response.data;
 * };
 *
 * // Example: Function to fetch all jobs
 * export const getJobs = async (): Promise<Job[]> => {
 *   const response = await apiClient.get<Job[]>('/jobs');
 *   return response.data;
 * };
 * ```
 */
export default apiClient;
```