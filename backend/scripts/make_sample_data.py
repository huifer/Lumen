"""生成一组离线测试样本（图片 + 文档），方便一键跑通 demo。

用法: python scripts/make_sample_data.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def red_product_shot(path: Path) -> None:
    img = Image.new("RGB", (960, 600), (214, 32, 42))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 900, 540], fill=(248, 248, 250))
    d.rectangle([60, 60, 900, 130], fill=(30, 30, 36))
    d.text((96, 88), "Product Launch", fill=(255, 255, 255))
    for i in range(3):
        y = 180 + i * 110
        d.rectangle([96, y, 520, y + 70], fill=(228, 228, 235))
        d.text((110, y + 25), f"Feature card {i + 1}", fill=(40, 40, 46))
        d.rectangle([560, y, 860, y + 70], fill=(214, 32, 42))
    img.save(path)


def sunset_beach(path: Path) -> None:
    img = Image.new("RGB", (900, 600), (250, 176, 90))
    d = ImageDraw.Draw(img)
    d.ellipse([380, 120, 520, 260], fill=(255, 236, 170))
    for y in range(300, 600):
        t = (y - 300) / 300
        d.line([(0, y), (900, y)], fill=(int(40 + 120 * t), int(120 + 60 * t), int(190 - 20 * t)))
    for y in range(240, 310):
        t = (y - 240) / 70
        d.line([(0, y), (900, y)], fill=(int(250 - 60 * t), int(170 + 20 * t), int(90 + 40 * t)))
    img.save(path)


def dark_dashboard(path: Path) -> None:
    img = Image.new("RGB", (1280, 720), (17, 19, 26))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 240, 720], fill=(24, 27, 36))
    for i in range(6):
        d.rectangle([40, 90 + i * 50, 200, 118 + i * 50], fill=(52, 58, 74))
    for i in range(4):
        x = 300 + (i % 2) * 480
        y = 60 + (i // 2) * 280
        d.rectangle([x, y, x + 420, y + 220], fill=(30, 34, 45))
        d.rectangle([x + 30, y + 150, x + 300, y + 190], fill=(88, 166, 255))
    img.save(path)


def blue_gradient(path: Path) -> None:
    img = Image.new("RGB", (800, 600))
    d = ImageDraw.Draw(img)
    for y in range(600):
        t = y / 600
        d.line([(0, y), (800, y)], fill=(int(20 + 40 * t), int(60 + 90 * t), int(180 + 40 * t)))
    d.ellipse([280, 180, 520, 420], fill=(240, 240, 250))
    img.save(path)


def minimal_docx(path: Path, title: str, paragraphs: list[str]) -> None:
    """手写一个最小可用的 docx（OOXML）。"""
    body = "".join(f"<w:p><w:r><w:t xml:space='preserve'>{p}</w:t></w:r></w:p>" for p in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    red_product_shot(SAMPLE_DIR / "红色背景产品截图.png")
    sunset_beach(SAMPLE_DIR / "海边日落.png")
    dark_dashboard(SAMPLE_DIR / "深色数据看板截图.png")
    blue_gradient(SAMPLE_DIR / "蓝色渐变背景图.png")

    (SAMPLE_DIR / "项目计划.txt").write_text(
        "项目计划\n\n"
        "第一阶段：完成产品需求评审与竞品调研。\n"
        "第二阶段：开发本地文件检索引擎，包含采集、理解、索引、检索四个模块。\n"
        "第三阶段：接入 Gemini 多模态模型生成图片描述与标签。\n"
        "第四阶段：上线 Web 界面，支持自然语言搜索图片与文档。\n"
        "预算说明：发票与报销材料请统一提交给财务部，财务会在七个工作日内完成付款流程。\n"
        "里程碑：八月底完成灰度发布，九月正式上线。\n",
        encoding="utf-8",
    )

    (SAMPLE_DIR / "发票说明.txt").write_text(
        "发票与报销说明\n\n"
        "本月发票共 12 张，金额合计 86400 元。\n"
        "增值税专用发票需在开具后 30 天内提交认证。\n"
        "差旅发票请附行程单，电子发票下载链接见附件。\n",
        encoding="utf-8",
    )

    (SAMPLE_DIR / "会议纪要.md").write_text(
        "# 产品评审会议纪要\n\n"
        "- 时间：周四下午\n- 参与人：产品、设计、研发\n\n"
        "## 结论\n"
        "1. 优先做自然语言搜索图片的能力。\n"
        "2. 离线模式必须可用，避免数据上传。\n"
        "3. Gemini Key 由环境变量注入，不写进代码仓库。\n",
        encoding="utf-8",
    )

    minimal_docx(
        SAMPLE_DIR / "合同摘要.docx",
        "合同摘要",
        [
            "合同摘要：本地多模态检索系统采购合同",
            "第一条 标的：本地多模态文件检索系统软件授权与实施服务。",
            "第二条 合同金额：人民币 128000 元，含一年期维保。",
            "第三条 付款方式：合同签订后预付 30%，验收合格后支付 60%，余款 10% 质保期满支付。",
            "第四条 交付时间：合同生效后 30 个工作日内完成部署与培训。",
        ],
    )

    print(f"样本已生成: {SAMPLE_DIR}")
    for p in sorted(SAMPLE_DIR.iterdir()):
        print(" -", p.name)


if __name__ == "__main__":
    main()
