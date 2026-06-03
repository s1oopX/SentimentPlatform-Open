from io import BytesIO

from django.conf import settings


BATCH_ANALYSIS_SUPPORTED_FORMATS = (".xlsx", ".txt")
_DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# ZIP file magic bytes — all .xlsx files are ZIP archives
_XLSX_MAGIC = b"PK\x03\x04"


class AnalysisValidationError(ValueError):
    """analysis 模块的参数或文件校验异常。"""


def _get_max_batch_records():
    from apps.admin_panel.infra.automation.system_config import get_max_batch_records
    return get_max_batch_records()


def _validate_file_magic_bytes(uploaded_file, expected_format):
    """Validate file content matches the claimed format by checking magic bytes.

    Prevents polyglot attacks where a malicious file is renamed with an
    allowed extension (e.g. renaming an HTML file to .xlsx).
    """
    if expected_format == ".xlsx":
        header = uploaded_file.read(4)
        uploaded_file.seek(0)
        if not header.startswith(_XLSX_MAGIC):
            raise AnalysisValidationError(
                "文件内容与 Excel(.xlsx) 格式不匹配，请上传有效的 Excel 文件"
            )


def parse_batch_comments(uploaded_file):
    comments = []
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", _DEFAULT_MAX_UPLOAD_SIZE)
    if uploaded_file.size > max_size:
        raise AnalysisValidationError(
            f"文件大小超过限制 ({max_size // 1024 // 1024}MB)"
        )

    file_name = uploaded_file.name.lower()
    max_rows = _get_max_batch_records()

    if file_name.endswith(BATCH_ANALYSIS_SUPPORTED_FORMATS[1]):
        try:
            for raw_line in uploaded_file:
                try:
                    line = raw_line.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise AnalysisValidationError("TXT 文件必须使用 UTF-8 编码") from exc
                if line:
                    comments.append(line)
                if len(comments) >= max_rows:
                    break
        except AnalysisValidationError:
            raise
        except Exception as exc:
            raise AnalysisValidationError(f"TXT 解析失败：{str(exc)}") from exc
    elif file_name.endswith(BATCH_ANALYSIS_SUPPORTED_FORMATS[0]):
        _validate_file_magic_bytes(uploaded_file, ".xlsx")
        try:
            import openpyxl

            workbook = openpyxl.load_workbook(BytesIO(uploaded_file.read()), read_only=True)
            try:
                worksheet = workbook.active
                for row in worksheet.iter_rows(min_row=2, values_only=True):
                    if row and row[0]:
                        comments.append(str(row[0]).strip())
                    if len(comments) >= max_rows:
                        break
            finally:
                workbook.close()
        except AnalysisValidationError:
            raise
        except Exception as exc:
            raise AnalysisValidationError(f"Excel 解析失败：{str(exc)}") from exc
    else:
        raise AnalysisValidationError("只支持 Excel(.xlsx) 和 TXT 格式文件")

    return [content for content in comments if content]
