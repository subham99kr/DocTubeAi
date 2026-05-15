export const YOUTUBE_REGEX =
  /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/;

export function isValidYoutubeUrl(
  url: string
) {
  return YOUTUBE_REGEX.test(url);
}

export function isPdfFile(
  file: File
) {
  return (
    file.type ===
    "application/pdf"
  );
}