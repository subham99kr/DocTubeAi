const TOKEN_KEY = "access_token";

const USER_KEY = "user";

export function saveToken(
  token: string
) {
  localStorage.setItem(
    TOKEN_KEY,
    token
  );
}

export function getToken() {
  return localStorage.getItem(
    TOKEN_KEY
  );
}

export function removeToken() {
  localStorage.removeItem(
    TOKEN_KEY
  );
}

export function saveUser(user: any) {
  localStorage.setItem(
    USER_KEY,
    JSON.stringify(user)
  );
}

export function getUser() {
  const user =
    localStorage.getItem(USER_KEY);

  if (!user) return null;

  return JSON.parse(user);
}

export function removeUser() {
  localStorage.removeItem(USER_KEY);
}