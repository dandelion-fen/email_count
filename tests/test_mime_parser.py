"""
MIME 解析测试
"""
import pytest
from tests.conftest import (
    make_email, make_gbk_email, make_multipart_email,
    AUTO_REPLY, BOUNCE_EMAIL, MY_EMAIL,
)
from src.mime_parser import parse_mime_message, extract_new_content


class TestMimeDecoding:
    """测试1-3: 中文主题解码、GBK/UTF-8正文、HTML正文"""

    def test_utf8_subject_decoding(self):
        """测试 UTF-8 中文主题解码"""
        raw = make_email(subject="【硕士保研自荐】湖北工业大学-杜子坤")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert "硕士保研自荐" in parsed.subject
        assert "杜子坤" in parsed.subject

    def test_gbk_email_parsing(self):
        """测试 GBK 编码邮件解析"""
        raw = make_gbk_email(subject="保研自荐信", body="您好，我是杜子坤")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert "保研" in parsed.subject
        assert "杜子坤" in parsed.body_text

    def test_html_body_extraction(self):
        """测试 HTML 正文提取"""
        raw = make_email(
            body="<html><body><p>欢迎报名</p><script>alert(1)</script></body></html>",
            is_html=True,
        )
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert "欢迎报名" in parsed.body_text or "欢迎报名" in parsed.body_html_text
        assert "alert" not in parsed.body_html_text  # script should be removed

    def test_multipart_email(self):
        """测试 multipart 邮件"""
        raw = make_multipart_email(text_body="纯文本", html_body="<p>HTML内容</p>")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert "纯文本" in parsed.body_text


class TestAutoReplyDetection:
    """测试7: 自动回复排除"""

    def test_auto_reply_detected(self):
        """自动回复邮件应被标记"""
        parsed = parse_mime_message(AUTO_REPLY, my_email=MY_EMAIL)
        assert parsed.is_auto_reply is True

    def test_normal_reply_not_auto(self):
        """正常回复不应被误判为自动回复"""
        raw = make_email(
            body="杜同学你好，欢迎报名我们夏令营。",
            subject="Re: 保研自荐",
        )
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert parsed.is_auto_reply is False


class TestBounceDetection:
    """测试8: 退信排除"""

    def test_bounce_detected(self):
        """退信应被标记"""
        parsed = parse_mime_message(BOUNCE_EMAIL, my_email=MY_EMAIL)
        assert parsed.is_bounce is True

    def test_normal_not_bounce(self):
        """正常邮件不应被标记为退信"""
        raw = make_email(body="你好")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert parsed.is_bounce is False


class TestContentSeparation:
    """测试正文分离"""

    def test_extract_new_content(self):
        body = "谢谢你的申请。\n\n> 原始邮件内容\n> 这是引用"
        new, quoted = extract_new_content(body)
        assert "谢谢" in new

    def test_extract_with_original_marker(self):
        body = "好的收到。\n\n--- 原始邮件 ---\n之前的内容"
        new, quoted = extract_new_content(body)
        assert "好的收到" in new


class TestSentByMe:
    """测试发件人识别"""

    def test_sent_by_me(self):
        raw = make_email(from_addr=MY_EMAIL, from_name="Test")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert parsed.is_sent_by_me is True

    def test_not_sent_by_me(self):
        raw = make_email(from_addr="other@example.com")
        parsed = parse_mime_message(raw, my_email=MY_EMAIL)
        assert parsed.is_sent_by_me is False
