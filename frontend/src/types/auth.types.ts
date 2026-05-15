export interface User {
  name: string;
  email?: string;
  picture?: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}