"""Tool for downloading research paper PDFs."""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.research.paper_store import PaperStore


class DownloadPaperPdfTool(Tool):
    """Download a paper PDF from arXiv or a direct URL, save to workspace, and register in paper library."""

    name = "download_paper_pdf"
    description = (
        "Download a paper PDF from arXiv or a direct PDF URL. "
        "The PDF is saved to the workspace research directory and optionally registered in the paper library. "
        "Use this after finding a paper to get its full text for parsing."
    )

    parameters = {
        "type": "object",
        "properties": {
            "arxiv_id": {
                "type": "string",
                "description": "arXiv ID to download. E.g. '2401.12345'. Either arxiv_id or url must be provided.",
            },
            "url": {
                "type": "string",
                "description": "Direct PDF URL to download. Either arxiv_id or url must be provided.",
            },
            "paper_id": {
                "type": "integer",
                "description": "Optional existing paper ID in the library to associate with this download.",
            },
            "filename": {
                "type": "string",
                "description": "Optional custom filename. Defaults to {arxiv_id}.pdf or extracted from URL.",
            },
        },
        "required": [],
    }

    def __init__(
        self,
        paper_store: PaperStore,
        download_dir: Path | str | None = None,
    ):
        self.paper_store = paper_store
        self.download_dir = Path(download_dir) if download_dir else Path.home() / ".nanobot" / "workspace" / "research" / "pdfs"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        arxiv_id: str = "",
        url: str = "",
        paper_id: int = 0,
        filename: str = "",
    ) -> str:
        if not arxiv_id and not url:
            return "Error: Please provide either arxiv_id or url."

        # Resolve download URL
        if arxiv_id:
            arxiv_id = arxiv_id.strip()
            if "arxiv.org/abs/" in arxiv_id:
                arxiv_id = arxiv_id.split("/")[-1]
            if "arxiv.org/pdf/" in arxiv_id:
                arxiv_id = arxiv_id.split("/")[-1].replace(".pdf", "")
            download_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            default_filename = f"{arxiv_id}.pdf"
        else:
            download_url = url.strip()
            parsed = urlparse(download_url)
            default_filename = Path(parsed.path).name or "paper.pdf"

        # Resolve filename
        save_name = filename.strip() or default_filename
        if not save_name.endswith(".pdf"):
            save_name += ".pdf"

        save_path = self.download_dir / save_name

        # Download
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                response = await client.get(download_url)
                response.raise_for_status()
                save_path.write_bytes(response.content)
        except Exception as e:
            logger.error(f"Failed to download PDF from {download_url}: {e}")
            return f"Error: Failed to download PDF: {str(e)}"

        # Update paper library if paper_id provided
        if paper_id:
            paper = self.paper_store.get_paper(paper_id)
            if paper:
                paper.pdf_path = str(save_path)
                self.paper_store.add_paper(paper)
                logger.info(f"Updated paper {paper_id} with PDF path: {save_path}")
            else:
                return f"Warning: Paper {paper_id} not found. PDF saved to {save_path}"

        file_size = save_path.stat().st_size
        return (
            f"PDF downloaded successfully.\n"
            f"- Source: {download_url}\n"
            f"- Saved to: {save_path}\n"
            f"- File size: {file_size / 1024:.1f} KB\n"
            f"Next step: Use parse_pdf_mineru with paths=['{save_path}'] to extract text."
        )
