export function saveToStorage(
  key: string,
  value: any
) {
  localStorage.setItem(
    key,
    JSON.stringify(value)
  );
}

export function getFromStorage<T>(
  key: string
): T | null {
  const item =
    localStorage.getItem(key);

  if (!item) {
    return null;
  }

  return JSON.parse(item);
}

export function removeFromStorage(
  key: string
) {
  localStorage.removeItem(key);
}