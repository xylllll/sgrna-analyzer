# sgRNA Analyzer v2.0 - 完全 Windows 原生版

从测序文件（R1/R2 FASTQ）一键生成完整的 sgRNA 文库分析 HTML 报告。

## 🎯 2.0 版改进（相比 1.0）

**彻底摆脱 WSL 依赖，纯 Windows 运行！**

| 组件 | 1.0 (WSL版) | 2.0 (Windows原生) |
|------|------------|-------------------|
| 质控 (fastp) | 需在 WSL 装 fastp | ✅ **纯 Python 实现**（内置） |
| 双端拼接 (FLASH) | WSL 环境 | Windows conda 环境 |
| BLAST 比对 | WSL 环境 | Windows 环境（NCBI 官方包） |
| 运行环境 | 必须先装 WSL + conda | 仅需 Python + 两个工具 |
| 启动速度 | 慢（WSL 冷启动 3-6s） | 快（无 WSL 开销） |
| 中文路径/编码问题 | 常出问题 | 无此问题 |

## 🖥️ Windows 用户快速开始

**无需 Linux 知识，双击运行！**

### 方式一：直接运行 Python 脚本

1. 确保电脑已安装 Python 3.9+
2. 双击 `sgRNA_Analyzer.pyw` 启动图形界面
3. 首次运行自动检测环境 → 若缺少工具按提示安装
4. 选择测序文件 → 点击"开始分析"
5. 分析完成后点击"打开报告"查看结果

> 提示：如果 `.pyw` 文件无法双击打开，右键 → 打开方式 → Python

### 方式二：打包为单个 EXE（无需安装 Python）

```bash
pip install pyinstaller
python build_exe.py
# 在 dist/ 目录找到 sgRNA_Analyzer.exe，双击运行即可
```

### 主界面说明

```
┌──────────────────────────────────────────┐
│  🧬 sgRNA 文库测序分析工具 v2.0           │
│                                          │
│  ┌─ 输入文件 ─────────────────────────┐  │
│  │ Read 1 (R1): [______] [浏览]       │  │
│  │ Read 2 (R2): [______] [浏览]       │  │
│  │ 参考库 FASTA: [______] [浏览]      │  │
│  └────────────────────────────────────┘  │
│                                          │
│  样品名称: [NC48]    线程数: [4]         │
│                                          │
│  [▶ 开始分析]  [⏹ 停止]                 │
│                                          │
│  ██████████████░░░░░░ 65%               │
│  正在运行: BLAST 比对...                 │
│                                          │
│  ┌─ 运行日志 (实时) ──────────────────┐  │
│  │ ✅ fastp 完成                       │  │
│  │ ✅ FLASH 拼接完成                   │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [📄 打开报告]  [📁 打开输出目录]        │
└──────────────────────────────────────────┘
```

- **文件选择**: 支持 .fq.gz / .fastq.gz / .fasta 格式
- **进度条**: 实时显示当前分析步骤
- **日志窗口**: 彩色日志，错误/警告/成功一目了然
- **配置记忆**: 选择过的文件路径自动保存，下次自动填充
- **环境向导**: 缺什么装什么，全程一键操作

## 功能概述

```
测序文件 (R1.fq.gz, R2.fq.gz)  +  参考库 (NC50.fasta)
                         ↓
              sgRNA Analyzer 自动分析
                         ↓
              📄 HTML 分析报告 (含图表+统计)
```

### 自动完成的步骤

1. **fastp 质量控制** — 去除低质量 reads、adapter 剪切
2. **FLASH 双端拼接** — 将 R1/R2 reads 拼接为完整 sgRNA 序列
3. **序列提取与去冗余** — 提取拼接序列、统计唯一序列
4. **BLAST 比对** — 将测序序列比对到参考 sgRNA 库
5. **覆盖度与均一性统计** — 计算文库覆盖度和 p10/p90 均一性
6. **图表生成** — Insert Size分布、碱基质量、碱基含量、核密度图、累积分布图
7. **HTML 报告** — 包含所有统计数据和图表的完整报告

### 输出

- **`{样品名}_sgRNA_report.html`** — 完整的分析报告（单文件，图片内嵌，可直接分享）
- **`results/`** — 中间分析文件（sgRNA_counts.txt 等）
- **`figures/`** — PNG 图表文件

---

## 环境要求

### 系统要求
- Windows 10/11 / Linux / macOS
- Python ≥ 3.9

### 外部工具（仅需 2 个）

本软件质控功能为**纯 Python 实现**，无需安装 fastp。只需安装：

```bash
# Windows 推荐使用 Miniconda (conda-forge)
conda install -c conda-forge flash
conda install -c bioconda blast

# 或 BLAST+ 也可用 NCBI 官方 Windows 安装包
# https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/
```

### Python 依赖

```bash
pip install -r requirements.txt
# 或
pip install matplotlib numpy scipy jinja2 pandas
```

---

## 安装

```bash
# 克隆或下载项目
cd sgRNA_analyzer

# 安装
pip install -e .

# 验证安装
sgrna-analyze --help
```

---

## 使用方法

### 基本用法

```bash
sgrna-analyze \
    --r1 data/sample_R1.fq.gz \
    --r2 data/sample_R2.fq.gz \
    --ref ref/NC50.fasta \
    --name NC48 \
    --outdir ./output
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--r1` | Read 1 FASTQ 文件 (必选) | - |
| `--r2` | Read 2 FASTQ 文件 (必选) | - |
| `--ref` | 参考 sgRNA 库 FASTA 文件 (必选) | - |
| `--name` | 样品名称 | `sample` |
| `--outdir` | 输出目录 | `./output` |
| `--threads` | 并行线程数 | `4` |

### 高级参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--blast-evalue` | BLAST e-value 阈值 | `1.0` |
| `--blast-identity` | BLAST 最小 identity % | `100.0` |
| `--blast-align-length` | BLAST 最小比对长度 | `20` |
| `--flash-min-overlap` | FLASH 最小 overlap | `10` |
| `--flash-max-overlap` | FLASH 最大 overlap | `150` |

### 断点续跑

当某个步骤已完成后，可以跳过它重新运行：

```bash
sgrna-analyze --r1 ... --r2 ... --ref ... --skip-fastp --skip-flash
```

---

## 项目目录结构

```
sgRNA_analyzer/
├── sgrna_analyzer/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # 命令行入口
│   ├── config.py           # 配置管理
│   ├── pipeline.py         # 主流程编排
│   ├── modules/
│   │   ├── fastp_runner.py     # fastp 质控
│   │   ├── flash_runner.py     # FLASH 拼接
│   │   ├── blast_runner.py     # BLAST 比对
│   │   ├── sequence_tools.py   # 序列处理
│   │   ├── stats.py            # 统计分析
│   │   ├── plotter.py          # 绘图(matplotlib)
│   │   └── reporter.py         # 报告生成
│   └── templates/
│       └── report.html     # Jinja2 报告模板
├── setup.py
├── requirements.txt
└── README.md
```

---

## 文件准备

### 输入文件格式

**测序文件**：标准 FASTQ 格式（支持 `.fq.gz` / `.fastq.gz` / `.fq` / `.fastq`）

```
@SEQ_ID
GATCGGAAGAGCACACGTCTG...
+
IIIIIIIIIIIIIIIIIIII...
```

**参考 sgRNA 库**：标准 FASTA 格式

```
>sgRNA_001
GATCGGAAGAGCACACGTCTG
>sgRNA_002
CGTACGATCGACTGACGTACG
...
```

---

## 报告内容说明

生成的 HTML 报告包含：

| 章节 | 内容 |
|------|------|
| 1. 质控摘要 | Clean reads/bases、Q30、GC 含量 |
| 2. 质量评估图 | Insert Size 分布、碱基质量、碱基含量 |
| 3. 覆盖度统计 | 参考库总数、检测数、覆盖度% |
| 4. 均一性 | p10、p90、p90/p10 比值 |
| 5. sgRNA 丰度表 | 每个 sgRNA 的 reads 数和占比 |
| 6. 丰度分布图 | 核密度图、累积分布图 |
| 7. 结论 | 自动评估覆盖度和均一性是否达标 |

---

## 常见问题

### Q: 中文在图表中显示为方块？
安装中文字体：
```bash
# Ubuntu/Debian
sudo apt install fonts-wqy-microhei fonts-wqy-zenhei

# CentOS/RHEL
sudo yum install wqy-microhei-fonts wqy-zenhei-fonts
```

### Q: FLASH/BLAST 未找到？
本软件质控为纯 Python 实现，无需 fastp。缺失 FLASH/BLAST 时：
```bash
conda install -c conda-forge flash
conda install -c bioconda blast
```

### Q: Windows 下能运行吗？
**完全支持。** 2.0 版本为 Windows 原生设计，无需 WSL。
只需安装 Python 和 FLASH/BLAST 两个工具即可运行完整管线。

---

## 免责声明

- 本软件由 **许逸伦** 开发，部分代码由 **AI 辅助编写**，并经过人工审核与验证（符合《生成式人工智能服务管理暂行办法》要求）。
- 本软件按"原样"(AS-IS) 提供，不附带任何担保；作者不对因使用本软件产生的直接或间接损失承担责任。
- **仅供科研与教学使用**，分析结果不构成医疗、临床诊断或治疗建议，不得用于临床决策。
- 涉及人类受试者或敏感数据的研究，使用者应自行确保符合伦理审批、知情同意及数据保护法律法规。
- 依赖工具各自遵守其许可条款（fastp: MIT，FLASH: GPLv2，BLAST+: 公有领域）。

完整声明见 [`DISCLAIMER.md`](DISCLAIMER.md)。

---

## 许可

MIT License (Copyright © 2026 许逸伦)

*本声明不构成法律意见，如有需要请咨询专业律师。*
