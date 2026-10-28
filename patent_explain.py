#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patent-tech-explain

把专利文本翻译成工程师能看懂的技术语言。

做法：把专利全文按段落编号，交给任意 OpenAI 兼容模型，要求它输出结构化的
技术解读，并且每一条结论都必须标注原文段落号，方便逐条回溯核对。

只依赖 Python 标准库，不需要 pip install。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PROMPT = HERE / "prompts" / "explain.md"

CITE_RE = re.compile(r"【P(\d+)】")
PARA_SPLIT_RE = re.compile(r"\n\s*\n")

STYLE_HINT = {
    "full": "完整版：八个部分全部输出，每部分都要有实质内容。",
    "brief": "精简版：只输出「一句话结论 / 技术问题 / 技术方案 / 关键创新点」四部分，其余省略。",
}


def die(msg: str) -> "None":
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(1)


def read_source(args) -> tuple[str, str]:
    """返回 (正文, 来源描述)。"""
    if args.stdin:
        return sys.stdin.read(), "标准输入"
    if not args.text:
        die("请用 --text <文件> 或 --stdin 指定专利文本")
    path = Path(args.text)
    if not path.exists():
        die(f"找不到文件: {args.text}")
    return path.read_text(encoding="utf-8"), str(path)


def segment(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]


def number_paragraphs(paras: list[str]) -> str:
    return "\n\n".join(f"【P{i}】{p}" for i, p in enumerate(paras, 1))


def build_prompt(template: str, numbered: str, style: str) -> str:
    return (
        template.replace("{numbered_text}", numbered)
        .replace("{style}", style)
        .replace("{style_hint}", STYLE_HINT.get(style, STYLE_HINT["full"]))
    )


def call_llm(
    messages: list[dict],
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 240,
    retries: int = 2,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.3},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_err = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = f"HTTP {exc.code}: {body}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except Exception as exc:  # 网络中断、超时、JSON 异常
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
    die(f"调用模型失败（{model} @ {url}）：{last_err}")
    return ""  # 不可达，仅为类型完整性


def verify_citations(answer: str, total: int) -> tuple[int, list[int]]:
    cited = {int(n) for n in CITE_RE.findall(answer)}
    valid = sorted(n for n in cited if 1 <= n <= total)
    invalid = sorted(n for n in cited if not (1 <= n <= total))
    uncited = [n for n in range(1, total + 1) if n not in set(valid)]
    if invalid:
        print(f"[警告] 回答引用了不存在的段落号: {invalid}", file=sys.stderr)
    return len(valid), uncited


def main() -> None:
    ap = argparse.ArgumentParser(
        description="把专利文本翻译成工程师能看懂的技术语言",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python patent_explain.py --text examples/sample_patent.md\n"
            "  python patent_explain.py --text patent.txt --style brief --out 解读.md\n"
            "  OPENAI_BASE_URL=http://127.0.0.1:3000/v1 MODEL=deepseek-v4-pro \\\n"
            "    python patent_explain.py --text patent.txt\n"
        ),
    )
    ap.add_argument("--text", help="专利文本文件路径（.md/.txt）")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取正文")
    ap.add_argument("--out", default="output.md", help="输出 Markdown 路径（默认 output.md）")
    ap.add_argument("--style", choices=sorted(STYLE_HINT), default="full", help="输出详细程度")
    ap.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"), help="模型名")
    ap.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI 兼容端点",
    )
    ap.add_argument("--prompt", default=str(DEFAULT_PROMPT), help="提示词模板路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印组装好的提示词，不调用模型")
    args = ap.parse_args()

    text, source = read_source(args)
    paras = segment(text)
    if len(paras) < 3:
        die("正文段落太少（<3），确认文件是否读到内容")
    numbered = number_paragraphs(paras)

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        die(f"找不到提示词模板: {prompt_path}")
    prompt = build_prompt(prompt_path.read_text(encoding="utf-8"), numbered, args.style)

    if args.dry_run:
        print(prompt)
        print(
            f"\n[dry-run] 段落 {len(paras)} 个，提示词 {len(prompt)} 字符，未调用模型",
            file=sys.stderr,
        )
        return

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        die("缺少 OPENAI_API_KEY 环境变量")

    print(f"[信息] 模型 {args.model} | 段落 {len(paras)} | 来源 {source}", file=sys.stderr)
    answer = call_llm(
        [{"role": "user", "content": prompt}],
        base_url=args.base_url,
        api_key=api_key,
        model=args.model,
    )

    n_cited, uncited = verify_citations(answer, len(paras))

    header = (
        f"<!-- 由 patent-tech-explain 生成 | 模型 {args.model} "
        f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        f"> 本文件由模型生成，结论须对照原文逐条核对。工具不做专利性判断，"
        f"也不构成法律意见。\n\n"
    )
    out = Path(args.out)
    out.write_text(header + answer.strip() + "\n", encoding="utf-8")

    print(
        f"[完成] 已写入 {out} | 引用段落 {n_cited} 处 | 未引用段落 {len(uncited)} 个",
        file=sys.stderr,
    )
    if uncited:
        preview = ", ".join(f"P{n}" for n in uncited[:12])
        print(f"[提示] 未被任何结论引用的段落: {preview}", file=sys.stderr)


if __name__ == "__main__":
    main()
