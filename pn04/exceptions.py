"""
pn04 解析器专用异常

所有异常继承自 ParserError，便于上层统一捕获和处理。
"""


class ParserError(Exception):
    """解析器基础异常。所有解析阶段异常由此派生。"""

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class UnsupportedFormatError(ParserError):
    """不支持的文件格式。

    当 file_type 或文件扩展名不属于 PDF/HTML/IMAGE 时抛出。
    """

    def __init__(self, file_type: str | None = None, file_url: str | None = None) -> None:
        msg = f"不支持的文件格式: file_type={file_type}, file_url={file_url}"
        super().__init__(msg, detail={"file_type": file_type, "file_url": file_url})


class FileReadError(ParserError):
    """文件读取失败。

    当文件路径无效、文件不存在或读取权限不足时抛出。
    """

    def __init__(self, file_path: str, *, reason: str = "") -> None:
        msg = f"文件读取失败: {file_path}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, detail={"file_path": file_path, "reason": reason})


class FileNotFoundError_(ParserError):
    """文件不存在。

    注意：命名加下划线避免与内置 FileNotFoundError 冲突。
    """

    def __init__(self, file_path: str) -> None:
        super().__init__(
            f"文件不存在: {file_path}",
            detail={"file_path": file_path},
        )


class OCRError(ParserError):
    """OCR 识别失败。

    当图片预处理或 OCR 引擎调用失败时抛出。
    """

    def __init__(self, message: str = "OCR 识别失败", *, detail: dict | None = None) -> None:
        super().__init__(message, detail=detail)


class EmptyContentError(ParserError):
    """解析结果为空。

    当解析器成功运行但未提取到任何文本内容时抛出。
    """

    def __init__(self, parser_type: str, file_path: str | None = None) -> None:
        msg = f"解析结果为空: parser_type={parser_type}"
        if file_path:
            msg += f", file={file_path}"
        super().__init__(msg, detail={"parser_type": parser_type, "file_path": file_path})
