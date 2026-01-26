"""
File Processor Service

Обрабатывает загруженные файлы для добавления в контекст Claude.
Поддерживает текстовые файлы, изображения и PDF.
"""

import base64
import logging
import os
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Типы поддерживаемых файлов"""
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    UNSUPPORTED = "unsupported"


@dataclass
class ProcessedFile:
    """Результат обработки файла"""
    file_type: FileType
    filename: str
    content: str  # Текстовое содержимое или base64 для изображений
    mime_type: str
    size_bytes: int
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None


class FileProcessorService:
    """
    Сервис обработки файлов для добавления в контекст Claude.

    Поддерживаемые форматы:
    - Текстовые: .md, .txt, .py, .js, .ts, .json, .yaml, .yml, .toml, .xml, .html, .css, .go, .rs, .java, .kt
    - Изображения: .png, .jpg, .jpeg, .gif, .webp
    - PDF: .pdf (конвертация в текст)
    """

    # Ограничения размера
    MAX_TEXT_SIZE = 1 * 1024 * 1024  # 1 MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_PDF_SIZE = 2 * 1024 * 1024    # 2 MB

    # Поддерживаемые расширения
    TEXT_EXTENSIONS = {
        ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".html",
        ".css", ".scss", ".less", ".go", ".rs", ".java", ".kt",
        ".c", ".cpp", ".h", ".hpp", ".sh", ".bash", ".zsh",
        ".sql", ".graphql", ".vue", ".svelte", ".astro",
        ".dockerfile", ".env", ".gitignore", ".editorconfig",
        ".csv", ".ini", ".cfg", ".conf", ".log", ".rb", ".php",
        ".swift", ".m", ".mm", ".pl", ".pm", ".r", ".scala",
        ".clj", ".ex", ".exs", ".erl", ".hs", ".lua", ".nim",
        ".zig", ".v", ".d", ".f90", ".f95", ".jl", ".dart",
    }

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    PDF_EXTENSIONS = {".pdf"}

    IMAGE_MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    # Языки для подсветки синтаксиса
    LANG_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".less": "less",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".sql": "sql",
        ".graphql": "graphql",
        ".md": "markdown",
        ".vue": "vue",
        ".svelte": "svelte",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".scala": "scala",
        ".clj": "clojure",
        ".ex": "elixir",
        ".exs": "elixir",
        ".hs": "haskell",
        ".lua": "lua",
        ".dart": "dart",
        ".r": "r",
    }

    def detect_file_type(self, filename: str) -> FileType:
        """Определить тип файла по расширению"""
        ext = self._get_extension(filename)

        if ext in self.TEXT_EXTENSIONS:
            return FileType.TEXT
        elif ext in self.IMAGE_EXTENSIONS:
            return FileType.IMAGE
        elif ext in self.PDF_EXTENSIONS:
            return FileType.PDF
        else:
            # Проверка на файлы без расширения (Dockerfile, Makefile, etc.)
            basename = os.path.basename(filename).lower()
            if basename in {"dockerfile", "makefile", "rakefile", "gemfile", "procfile"}:
                return FileType.TEXT
            return FileType.UNSUPPORTED

    def _get_extension(self, filename: str) -> str:
        """Получить расширение файла в lowercase"""
        _, ext = os.path.splitext(filename.lower())
        return ext

    def validate_file(self, filename: str, size: int) -> Tuple[bool, Optional[str]]:
        """
        Валидация файла перед обработкой.

        Returns:
            Tuple[is_valid, error_message]
        """
        file_type = self.detect_file_type(filename)

        if file_type == FileType.UNSUPPORTED:
            ext = self._get_extension(filename) or "(нет расширения)"
            return False, f"Неподдерживаемый тип файла: {ext}"

        max_size = {
            FileType.TEXT: self.MAX_TEXT_SIZE,
            FileType.IMAGE: self.MAX_IMAGE_SIZE,
            FileType.PDF: self.MAX_PDF_SIZE,
        }.get(file_type, self.MAX_TEXT_SIZE)

        if size > max_size:
            max_mb = max_size / (1024 * 1024)
            return False, f"Файл слишком большой (максимум {max_mb:.1f} MB)"

        return True, None

    async def process_file(
        self,
        file_content: BytesIO,
        filename: str,
        mime_type: Optional[str] = None
    ) -> ProcessedFile:
        """
        Обработать файл и вернуть готовый для Claude контент.

        Args:
            file_content: Содержимое файла как BytesIO
            filename: Имя файла
            mime_type: MIME тип (опционально)

        Returns:
            ProcessedFile с готовым контентом
        """
        file_type = self.detect_file_type(filename)
        content_bytes = file_content.read()
        size = len(content_bytes)

        # Валидация
        is_valid, error = self.validate_file(filename, size)
        if not is_valid:
            return ProcessedFile(
                file_type=file_type,
                filename=filename,
                content="",
                mime_type=mime_type or "",
                size_bytes=size,
                error=error
            )

        try:
            if file_type == FileType.TEXT:
                content = self._process_text(content_bytes)
                mime = mime_type or "text/plain"
            elif file_type == FileType.IMAGE:
                content = self._process_image(content_bytes)
                ext = self._get_extension(filename)
                mime = mime_type or self.IMAGE_MIME_TYPES.get(ext, "image/png")
            elif file_type == FileType.PDF:
                content = await self._process_pdf(content_bytes)
                mime = mime_type or "application/pdf"
            else:
                return ProcessedFile(
                    file_type=file_type,
                    filename=filename,
                    content="",
                    mime_type="",
                    size_bytes=size,
                    error="Неподдерживаемый тип файла"
                )

            logger.info(f"Processed file: {filename} ({file_type.value}, {size} bytes)")

            return ProcessedFile(
                file_type=file_type,
                filename=filename,
                content=content,
                mime_type=mime,
                size_bytes=size
            )

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            return ProcessedFile(
                file_type=file_type,
                filename=filename,
                content="",
                mime_type=mime_type or "",
                size_bytes=size,
                error=f"Ошибка обработки: {str(e)}"
            )

    def _process_text(self, content_bytes: bytes) -> str:
        """Обработать текстовый файл"""
        # Попытка декодировать как UTF-8, затем latin-1 как fallback
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content_bytes.decode("latin-1")
            except UnicodeDecodeError:
                return content_bytes.decode("utf-8", errors="replace")

    def _process_image(self, content_bytes: bytes) -> str:
        """Обработать изображение - вернуть base64"""
        return base64.b64encode(content_bytes).decode("utf-8")

    async def _process_pdf(self, content_bytes: bytes) -> str:
        """
        Обработать PDF - извлечь текст.

        Требует pypdf или pdfplumber.
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content_bytes))
            text_parts = []

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Страница {i + 1} ---\n{page_text}")

            if not text_parts:
                return "[PDF: не удалось извлечь текст (возможно, отсканированный документ)]"

            return "\n\n".join(text_parts)

        except ImportError:
            logger.warning("pypdf not installed, PDF processing unavailable")
            return "[PDF: pypdf не установлен - содержимое недоступно. Установите: pip install pypdf]"
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return f"[PDF: ошибка извлечения текста - {str(e)}]"

    def format_for_prompt(
        self,
        processed_file: ProcessedFile,
        task_text: str = ""
    ) -> str:
        """
        Форматировать обработанный файл для добавления в prompt.

        Args:
            processed_file: Обработанный файл
            task_text: Текст задачи пользователя

        Returns:
            Отформатированный prompt с файлом
        """
        if processed_file.error:
            error_block = f"[Ошибка обработки файла {processed_file.filename}: {processed_file.error}]"
            if task_text:
                return f"{error_block}\n\n{task_text}"
            return error_block

        if processed_file.file_type == FileType.TEXT:
            # Для текстовых файлов - вставляем содержимое в код-блок
            lang = self._detect_language(processed_file.filename)
            file_block = f"📎 **Файл: {processed_file.filename}** ({processed_file.size_bytes // 1024} KB)\n```{lang}\n{processed_file.content}\n```"

            if task_text:
                return f"{file_block}\n\n---\n\n{task_text}"
            return file_block

        elif processed_file.file_type == FileType.IMAGE:
            # Для изображений - специальная пометка
            # Claude SDK может обрабатывать base64 изображения
            image_marker = f"[Изображение: {processed_file.filename}]"

            if task_text:
                return f"{image_marker}\n\n{task_text}"
            return image_marker

        elif processed_file.file_type == FileType.PDF:
            # PDF - извлеченный текст
            file_block = f"📎 **PDF: {processed_file.filename}** ({processed_file.size_bytes // 1024} KB)\n```\n{processed_file.content}\n```"

            if task_text:
                return f"{file_block}\n\n---\n\n{task_text}"
            return file_block

        return task_text

    def _detect_language(self, filename: str) -> str:
        """Определить язык для подсветки синтаксиса"""
        ext = self._get_extension(filename)
        return self.LANG_MAP.get(ext, "")

    def get_supported_extensions(self) -> dict:
        """Получить список поддерживаемых расширений по типам"""
        return {
            "text": sorted(self.TEXT_EXTENSIONS),
            "image": sorted(self.IMAGE_EXTENSIONS),
            "pdf": sorted(self.PDF_EXTENSIONS),
        }
