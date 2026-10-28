# patent-tech-explain

把专利文本翻译成工程师能看懂的技术语言。

## 这是干什么的

专利文本的写法是为法律服务的，不是为工程服务的。一份权利要求读完，工程师常常还得自己反推：它到底在解决什么问题、方案的关键在哪、哪些参数是必须满足的、哪些只是举例。

这个工具做一件事：读入专利全文，输出一份结构化技术解读，并且**每一条结论都标注原文段落号**，可以逐条回溯核对，不用盲信模型的总结。

输出的八个部分：

1. 一句话结论
2. 技术问题（现有技术的缺陷，以及在工程上的具体表现）
3. 技术方案（整体架构、核心流程、关键参数、实现依赖）
4. 关键创新点（结构创新 / 方法创新 / 参数优化分开说）
5. 权利要求逐条解读（保护范围 + 一句话人话）
6. 实施要点与边界（落地门槛、适用边界、已知代价）
7. 术语对照表（原文表述 ↔ 工程含义）
8. 原文覆盖度提示（哪里缺失、含糊、前后不一致）

## 快速开始

只依赖 Python 标准库，不用装任何第三方包，Python 3.9 以上即可。

```bash
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.openai.com/v1   # 可选，默认为官方端点
export MODEL=gpt-4o-mini                            # 可选

python patent_explain.py --text examples/sample_patent.md --out 解读.md
```

先看效果但不调用模型（打印组装好的提示词）：

```bash
python patent_explain.py --text examples/sample_patent.md --dry-run
```

只要四个部分，省 token：

```bash
python patent_explain.py --text patent.txt --style brief
```

从管道读入：

```bash
pbpaste | python patent_explain.py --stdin --out 解读.md
```

## 接入任意 OpenAI 兼容端点

脚本只认 `chat/completions` 协议，所以 OpenAI、Azure OpenAI、国内的 DeepSeek、通义、豆包，以及各类聚合网关都能直接用，改环境变量即可：

```bash
# DeepSeek 官方
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export MODEL=deepseek-chat

# 阿里云百炼（OpenAI 兼容模式）
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export MODEL=qwen-plus

# 本地或局域网内的任意网关
export OPENAI_BASE_URL=http://127.0.0.1:3000/v1
export MODEL=your-model
```

## 设计上的三个取舍

**段落编号 + 强制引用。** 输入先按空行切段并编号 `【P1】【P2】…`，提示词要求每条结论后标注来源。输出后脚本会统计引用覆盖率，告诉你哪些段落从头到尾没被任何结论用到——那些往往就是信息缺失或表述含糊的地方。

**不做两遍调用。** 一次性输出，不为「先提取再解释」拆成两轮。代价是长文本可能丢细节，收益是成本和延迟都可控。专利超过两万字时，建议先按「权利要求 + 具体实施方式」截取，再跑。

**不给法律结论。** 工具不判断新颖性、创造性、能否授权、是否侵权，也不评估专利质量。它只回答「这项技术是怎么做的」。判断性的事交给人。

## 输出示例

`examples/sample_output.md` 是一份真实生成的完整输出，输入是 `examples/sample_patent.md`（虚构示例），可以直接对照它判断这个工具值不值得用。

那份输出里，第八节「原文覆盖度提示」指出了几处原文自身的问题，例如：

- 权利要求写「超过 3 次」跳变，具体实施方式写「阈值取 3 次」，两者在「等于 3 次时是否触发」上不一致；
- 目标贴边距离 15 至 25 毫米，而红外量程下限 20 毫米、超声波量程下限 30 毫米，该距离下两路信号如何参与融合未作说明；
- 两个传感器相距 40 毫米，贴边 15 毫米时测量点不一致，原文未说明是否做坐标补偿。

这类问题人工读三遍也未必发现，是段落编号加逐条引用逼出来的。

（实际行文由模型生成，每次措辞会变，但结构与引用要求是固定的。）

## 限制

- 不自动下载专利全文。CNIPA、Google Patents、Espacenet 各有自己的抓取限制，交给使用者自己取文；本工具只负责解读。
- 不做 OCR。扫描版 PDF 请先转成文本。
- 模型可能误读或漏读，所以才有段落引用——**每一条都要对回原文**。
- 法律意见不在本工具范围内，涉及申请、无效、诉讼请找执业代理师或律师。

## 许可

MIT，见 LICENSE。
