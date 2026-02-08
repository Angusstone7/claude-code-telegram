"""
File Processor Service

Обрабатывает загруженные файлы для добавления в контекст Claude.
Поддерживает текстовые файлы, изображения, PDF и ZIP-архивы.
"""

import asyncio
import base64
import logging
import os
import zipfile
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Optional, Tuple, List

import aiofiles

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Типы поддерживаемых файлов"""
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    ZIP = "zip"
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
    saved_path: Optional[str] = None  # Путь к сохраненному файлу в рабочей директории

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
    - ZIP: .zip (распаковка и обработка содержимого)
    """

    # Ограничения размера
    MAX_TEXT_SIZE = 1 * 1024 * 1024  # 1 MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_PDF_SIZE = 2 * 1024 * 1024    # 2 MB
    MAX_ZIP_SIZE = 20 * 1024 * 1024   # 20 MB
    MAX_ZIP_EXTRACTED_SIZE = 10 * 1024 * 1024  # 10 MB total extracted text
    MAX_ZIP_FILES = 100  # Max files to process from archive

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
    ZIP_EXTENSIONS = {".zip"}

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
        elif ext in self.ZIP_EXTENSIONS:
            return FileType.ZIP
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
            FileType.ZIP: self.MAX_ZIP_SIZE,
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
            elif file_type == FileType.ZIP:
                content = await self._process_zip(content_bytes, filename)
                mime = mime_type or "application/zip"
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

    async def _process_zip(self, content_bytes: bytes, archive_name: str) -> str:
        """
        Обработать ZIP-архив — извлечь текстовое содержимое файлов.

        Рекурсивно обрабатывает файлы внутри архива:
        - Текстовые файлы: читает содержимое
        - Изображения/PDF/бинарные: только перечисляет
        - Вложенные ZIP: не распаковывает (только перечисляет)

        Returns:
            Отформатированный текст со всем содержимым архива
        """
        try:
            zip_buffer = BytesIO(content_bytes)

            if not zipfile.is_zipfile(zip_buffer):
                return "[ZIP: файл повреждён или не является ZIP-архивом]"

            zip_buffer.seek(0)

            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                # Security: check for zip bombs
                total_uncompressed = sum(info.file_size for info in zf.infolist() if not info.is_dir())
                if total_uncompressed > self.MAX_ZIP_EXTRACTED_SIZE * 5:
                    return (
                        f"[ZIP: архив слишком большой после распаковки "
                        f"({total_uncompressed / (1024*1024):.1f} MB). "
                        f"Максимум: {self.MAX_ZIP_EXTRACTED_SIZE * 5 / (1024*1024):.0f} MB]"
                    )

                file_entries = [
                    info for info in zf.infolist()
                    if not info.is_dir() and not info.filename.startswith('__MACOSX/')
                ]

                if not file_entries:
                    return "[ZIP: архив пуст]"

                # Sort by path for readability
                file_entries.sort(key=lambda x: x.filename)

                text_parts: List[str] = []
                skipped_files: List[str] = []
                total_extracted_size = 0
                processed_count = 0

                # Header
                text_parts.append(
                    f"📦 **ZIP-архив: {archive_name}** "
                    f"({len(file_entries)} файлов)\n"
                )

                for info in file_entries:
                    if processed_count >= self.MAX_ZIP_FILES:
                        remaining = len(file_entries) - processed_count
                        text_parts.append(
                            f"\n⚠️ Показано {processed_count} из {len(file_entries)} файлов "
                            f"(ещё {remaining} пропущено из-за лимита)"
                        )
                        break

                    fname = info.filename
                    fsize = info.file_size

                    # Determine file type by extension
                    ftype = self.detect_file_type(fname)

                    if ftype == FileType.TEXT:
                        # Check cumulative size limit
                        if total_extracted_size + fsize > self.MAX_ZIP_EXTRACTED_SIZE:
                            skipped_files.append(f"{fname} ({fsize // 1024} KB) — превышен лимит")
                            processed_count += 1
                            continue

                        try:
                            raw = zf.read(info.filename)
                            text_content = self._process_text(raw)
                            lang = self._detect_language(fname)

                            text_parts.append(
                                f"\n--- 📄 {fname} ({fsize // 1024} KB) ---\n"
                                f"```{lang}\n{text_content}\n```"
                            )
                            total_extracted_size += fsize
                        except Exception as e:
                            skipped_files.append(f"{fname} — ошибка чтения: {e}")

                    elif ftype == FileType.IMAGE:
                        skipped_files.append(f"🖼 {fname} ({fsize // 1024} KB) — изображение")

                    elif ftype == FileType.PDF:
                        # Try to extract text from PDF inside ZIP
                        if fsize <= self.MAX_PDF_SIZE:
                            try:
                                raw = zf.read(info.filename)
                                pdf_text = await self._process_pdf(raw)
                                text_parts.append(
                                    f"\n--- 📑 {fname} ({fsize // 1024} KB) ---\n"
                                    f"```\n{pdf_text}\n```"
                                )
                                total_extracted_size += len(pdf_text)
                            except Exception as e:
                                skipped_files.append(f"📑 {fname} — ошибка PDF: {e}")
                        else:
                            skipped_files.append(f"📑 {fname} ({fsize // 1024} KB) — PDF слишком большой")

                    elif ftype == FileType.ZIP:
                        skipped_files.append(f"📦 {fname} ({fsize // 1024} KB) — вложенный архив")

                    else:
                        skipped_files.append(f"❓ {fname} ({fsize // 1024} KB) — неподдерживаемый тип")

                    processed_count += 1

                # Add skipped files summary
                if skipped_files:
                    text_parts.append(
                        f"\n\n📋 **Пропущенные/бинарные файлы** ({len(skipped_files)}):\n"
                        + "\n".join(f"  • {s}" for s in skipped_files)
                    )

                return "\n".join(text_parts)

        except zipfile.BadZipFile:
            return "[ZIP: файл повреждён или не является ZIP-архивом]"
        except Exception as e:
            logger.error(f"ZIP extraction error: {e}")
            return f"[ZIP: ошибка обработки — {str(e)}]"

    def save_to_working_dir(
        self,
        processed_file: ProcessedFile,
        working_dir: str
    ) -> Optional[str]:
        """
        Сохранить файл в рабочую директорию проекта.

        Args:
            processed_file: Обработанный файл
            working_dir: Рабочая директория проекта

        Returns:
            Путь к сохраненному файлу или None при ошибке
        """
        try:
            # Создаём папку .uploads для временных файлов
            uploads_dir = os.path.join(working_dir, ".uploads")
            await asyncio.to_thread(os.makedirs, uploads_dir, exist_ok=True)

            file_path = os.path.join(uploads_dir, processed_file.filename)

            if processed_file.file_type == FileType.IMAGE:
                # Декодируем base64 и сохраняем
                image_data = base64.b64decode(processed_file.content)
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(image_data)
            else:
                # Текстовые файлы сохраняем как есть
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(processed_file.content)

            processed_file.saved_path = file_path
            logger.info(f"File saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error saving file to working dir: {e}")
            return None

    def format_for_prompt(
        self,
        processed_file: ProcessedFile,
        task_text: str = "",
        working_dir: Optional[str] = None
    ) -> str:
        """
        Форматировать обработанный файл для добавления в prompt.

        Args:
            processed_file: Обработанный файл
            task_text: Текст задачи пользователя
            working_dir: Рабочая директория для сохранения изображений

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
            # Для изображений - сохраняем в рабочую директорию и указываем путь
            if working_dir:
                saved_path = self.save_to_working_dir(processed_file, working_dir)
                if saved_path:
                    image_instruction = (
                        f"📎 **Изображение сохранено:** `{saved_path}`\n\n"
                        f"Используй Read tool чтобы прочитать и проанализировать это изображение.\n"
                        f"Путь к файлу: {saved_path}"
                    )
                    if task_text:
                        return f"{image_instruction}\n\n---\n\n**Задача пользователя:** {task_text}"
                    return image_instruction

            # Fallback если не удалось сохранить
            image_marker = f"[Изображение: {processed_file.filename} - не удалось сохранить для анализа]"
            if task_text:
                return f"{image_marker}\n\n{task_text}"
            return image_marker

        elif processed_file.file_type == FileType.PDF:
            # PDF - извлеченный текст
            file_block = f"📎 **PDF: {processed_file.filename}** ({processed_file.size_bytes // 1024} KB)\n```\n{processed_file.content}\n```"

            if task_text:
                return f"{file_block}\n\n---\n\n{task_text}"
            return file_block

        elif processed_file.file_type == FileType.ZIP:
            # ZIP - уже отформатированное содержимое архива
            file_block = processed_file.content

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
            "zip": sorted(self.ZIP_EXTENSIONS),
        }

    def format_multiple_files_for_prompt(
        self,
        files: list[ProcessedFile],
        task_text: str = "",
        working_dir: Optional[str] = None
    ) -> str:
        """
        Форматировать несколько файлов для добавления в prompt.

        Используется для медиагрупп (альбомов) - когда пользователь
        отправляет несколько файлов одним сообщением.

        Args:
            files: Список обработанных файлов
            task_text: Текст задачи пользователя
            working_dir: Рабочая директория для сохранения изображений

        Returns:
            Отформатированный prompt со всеми файлами
        """
        if not files:
            return task_text

        if len(files) == 1:
            # Один файл - используем обычный метод
            return self.format_for_prompt(files[0], task_text, working_dir)

        # Несколько файлов - формируем комбинированный prompt
        file_blocks = []

        for i, pf in enumerate(files, 1):
            if pf.error:
                file_blocks.append(f"📎 **Файл {i}: {pf.filename}** - Ошибка: {pf.error}")
                continue

            if pf.file_type == FileType.TEXT:
                lang = self._detect_language(pf.filename)
                block = f"📎 **Файл {i}: {pf.filename}** ({pf.size_bytes // 1024} KB)\n```{lang}\n{pf.content}\n```"
                file_blocks.append(block)

            elif pf.file_type == FileType.IMAGE:
                if working_dir:
                    saved_path = self.save_to_working_dir(pf, working_dir)
                    if saved_path:
                        block = (
                            f"📎 **Изображение {i}: {pf.filename}** сохранено в `{saved_path}`\n"
                            f"Используй Read tool для анализа: {saved_path}"
                        )
                        file_blocks.append(block)
                        continue

                # Fallback
                file_blocks.append(f"📎 **Изображение {i}: {pf.filename}** - не удалось сохранить")

            elif pf.file_type == FileType.PDF:
                block = f"📎 **PDF {i}: {pf.filename}** ({pf.size_bytes // 1024} KB)\n```\n{pf.content}\n```"
                file_blocks.append(block)

            elif pf.file_type == FileType.ZIP:
                # ZIP - уже отформатированное содержимое
                file_blocks.append(pf.content)

        # Объединяем все блоки
        files_section = "\n\n".join(file_blocks)

        if task_text:
            return f"{files_section}\n\n---\n\n**Задача пользователя:** {task_text}"

        return files_section

    def get_files_summary(self, files: list[ProcessedFile]) -> str:
        """
        Получить краткое описание списка файлов.

        Args:
            files: Список обработанных файлов

        Returns:
            Строка вида "3 файла: image1.jpg, image2.jpg, +1"
        """
        if not files:
            return "нет файлов"

        total = len(files)
        if total == 1:
            return files[0].filename

        # Показываем первые 2 имени, остальные как "+N"
        names = [f.filename for f in files[:2]]
        if total > 2:
            names.append(f"+{total - 2}")

        return f"{total} файлов: {', '.join(names)}"
