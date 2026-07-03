"""
pn04 图片 OCR 解析器

使用 Tesseract OCR 识别图片中的文字。
支持 PNG、JPG、BMP、TIFF、WebP 等常见图片格式。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pn04.exceptions import EmptyContentError, FileReadError, FileNotFoundError_, OCRError
from pn04.models import ParseConfig, ParseResult, ParserType

logger = logging.getLogger(__name__)

# 支持的图片扩展名
_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}


class ImageParser:
    """图片 OCR 解析器。

    使用 Pillow 进行图片预处理，pytesseract 进行 OCR 文字识别。
    默认支持中文+英文识别。

    Usage:
        parser = ImageParser(config=ParseConfig())
        result = parser.parse("/path/to/chart.png")
    """

    def __init__(self, config: ParseConfig | None = None) -> None:
        self.config = config or ParseConfig()

    def parse(self, file_path: str) -> ParseResult:
        """
        对图片文件执行 OCR 并返回识别文本。

        Args:
            file_path: 图片文件的本地路径

        Returns:
            ParseResult: 包含 OCR 识别文本和元数据

        Raises:
            FileNotFoundError_: 文件不存在
            FileReadError: 文件读取失败
            OCRError: OCR 识别失败
            EmptyContentError: 识别结果为空
        """
        self._validate_file(file_path)
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow 未安装，请执行: pip install Pillow")

        try:
            import pytesseract
        except ImportError:
            raise ImportError(
                "pytesseract 未安装，请执行: pip install pytesseract\n"
                "同时需要安装 Tesseract OCR 引擎: "
                "https://github.com/tesseract-ocr/tesseract"
            )

        try:
            image = Image.open(file_path)
            metadata: dict[str, Any] = {
                "file_path": file_path,
                "format": image.format,
                "size": image.size,
                "mode": image.mode,
            }

            # 预处理
            processed = self._preprocess(image)

            # OCR 识别
            try:
                text = pytesseract.image_to_string(
                    processed,
                    lang=self.config.ocr_lang,
                )
            except pytesseract.TesseractError as exc:
                raise OCRError(
                    f"Tesseract OCR 执行失败: {exc}",
                    detail={"file_path": file_path},
                ) from exc
            except Exception as exc:
                raise OCRError(
                    f"OCR 失败: {exc}",
                    detail={"file_path": file_path},
                ) from exc

            text = text.strip()

            if not text:
                raise EmptyContentError(
                    parser_type=ParserType.IMAGE.value,
                    file_path=file_path,
                )

            # 截断处理
            if len(text) > self.config.max_text_length:
                text = (
                    text[: self.config.max_text_length]
                    + f"\n\n[文本过长，已截断，原长度: {len(text)} 字符]"
                )

            return ParseResult(
                parser_type=ParserType.IMAGE,
                raw_text=text,
                metadata=metadata,
            )

        except (EmptyContentError, OCRError, FileNotFoundError_, FileReadError):
            raise
        except Exception as exc:
            raise FileReadError(file_path, reason=str(exc)) from exc

    def ocr_from_bytes(self, image_bytes: bytes) -> str:
        """
        从内存中的图片字节数据执行 OCR（用于 PDF 扫描页降级）。

        Args:
            image_bytes: PNG/JPEG 格式的图片字节数据

        Returns:
            OCR 识别的文本
        """
        try:
            from PIL import Image
            from io import BytesIO

            import pytesseract
        except ImportError:
            logger.warning("OCR 依赖未安装，跳过 OCR")
            return ""

        try:
            image = Image.open(BytesIO(image_bytes))
            processed = self._preprocess(image)
            text = pytesseract.image_to_string(
                processed,
                lang=self.config.ocr_lang,
            )
            return text.strip()
        except Exception as exc:
            logger.warning(f"OCR from bytes 失败: {exc}")
            return ""

    # ---- 内部方法 ----

    @staticmethod
    def _validate_file(file_path: str) -> None:
        """验证文件存在、可读、格式支持。"""
        if not os.path.exists(file_path):
            raise FileNotFoundError_(file_path)
        if not os.path.isfile(file_path):
            raise FileReadError(file_path, reason="路径不是文件")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise FileReadError(
                file_path,
                reason=f"不支持的图片格式: {ext}，支持: {_SUPPORTED_EXTENSIONS}",
            )

    def _preprocess(self, image: Any) -> Any:
        """
        图片预处理：增强 OCR 识别准确率。

        步骤: 转灰度 → 对比度增强 → 锐化 → 放大（小字体场景）
        """
        from PIL import ImageEnhance, ImageFilter

        # 1. RGBA → RGB → 灰度
        if image.mode == "RGBA":
            image = image.convert("RGBA")
            background = image.getchannel("A")
            bg = image.copy()
            bg.putalpha(background)
            image = bg.convert("RGB")
        if image.mode != "L":
            image = image.convert("L")

        # 2. 对比度增强
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # 3. 锐化
        image = image.filter(ImageFilter.SHARPEN)

        # 4. 放大（小图片）
        width, height = image.size
        if width < 800 or height < 800:
            scale = max(2, min(4, 1600 // min(width, height)))
            image = image.resize(
                (width * scale, height * scale),
                Image.LANCZOS,
            )

        return image
