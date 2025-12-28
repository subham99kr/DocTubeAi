import re
from bs4 import BeautifulSoup

async def run_web_scrape(url: str, http_client) -> str:
    """
    logic: Fetches a URL and returns LLM-friendly cleaned text.
    """
    try:
        response = await http_client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Remove absolute noise
        # Added 'iframe', 'header', and 'svg' which often contain junk data
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "svg"]):
            element.decompose()

        # 2. Strategic Text Extraction
        text = soup.get_text(separator="\n")

        # 3. Clean and Normalize
        clean_text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove trailing/leading whitespace from each line
        clean_text = "\n".join([line.strip() for line in clean_text.splitlines() if line.strip()])

        # 4. Truncate
        return clean_text[:6000]

    except Exception as e:
        return f"Error scraping {url}: {str(e)}"

