"""黄金数据集：简历 + JD + 人工标注的匹配评分与关键点。

每条样本：
- resume_text: 简历原文
- jd: 目标岗位描述
- ground_truth: {
    "score": 人工打分 0-100,
    "strengths": 关键优势（列表），
    "gaps": 关键差距（列表）
  }

覆盖场景：
- 高匹配（技能 + 经验完美对应）
- 中等匹配（部分技能对应，经验略差）
- 低匹配（技能栈不符 / 经验过浅）
- 边界情况（过度资深、转岗）
"""
from __future__ import annotations

GOLDEN_DATASET = [
    # -------- 1. 高匹配：资深后端 vs Python 后端岗 --------
    {
        "id": "high_match_backend",
        "resume_text": """
张三
邮箱: zhangsan@example.com | 电话: 13800001111
教育: 硕士，计算机科学，清华大学
工作年限: 5 年

技能：Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS

工作经历：
- 某互联网公司 后端工程师 (2019-2024)
  负责电商平台后端开发，日活 500 万用户
  技术栈: FastAPI + PostgreSQL + Redis + K8s
  实现了订单系统微服务化，QPS 提升 3 倍
""",
        "jd": """
招聘 Python 后端工程师
要求：
- 3 年以上 Python 开发经验
- 熟悉 FastAPI / Django
- 熟悉 PostgreSQL / Redis
- 有 Docker / K8s 经验优先
- 大厂背景优先
""",
        "ground_truth": {
            "score": 95,
            "strengths": ["5年经验超出要求", "FastAPI+PostgreSQL完全匹配", "有K8s实战", "大厂背景"],
            "gaps": [],
        },
    },
    # -------- 2. 中匹配：初级前端 vs 中级前端岗 --------
    {
        "id": "mid_match_frontend",
        "resume_text": """
李四
教育: 本科，软件工程
工作年限: 2 年

技能：JavaScript, React, HTML, CSS, Git

工作经历：
- 某创业公司 前端开发 (2022-2024)
  负责企业官网与后台管理系统前端
  技术栈: React + Ant Design
""",
        "jd": """
招聘中级前端工程师
要求：
- 3+ 年前端开发经验
- 精通 React / Vue
- 熟悉 TypeScript
- 有移动端 H5 经验
- 了解前端工程化（Webpack/Vite）
""",
        "ground_truth": {
            "score": 60,
            "strengths": ["React 技能匹配"],
            "gaps": ["仅2年经验未达3年", "缺 TypeScript", "无移动端经验", "无工程化提及"],
        },
    },
    # -------- 3. 低匹配：Java 后端 vs Python 后端岗 --------
    {
        "id": "low_match_skill_mismatch",
        "resume_text": """
王五
教育: 本科
工作年限: 4 年

技能：Java, Spring Boot, MyBatis, MySQL, Maven

工作经历：
- 某金融公司 Java 后端 (2020-2024)
  负责支付系统开发
""",
        "jd": """
招聘 Python 后端工程师
要求：
- 3 年以上 Python 开发经验
- 熟悉 FastAPI / Flask
- 熟悉 PostgreSQL
""",
        "ground_truth": {
            "score": 25,
            "strengths": ["后端经验4年", "有数据库经验"],
            "gaps": ["完全不会 Python", "技能栈Java与要求不符"],
        },
    },
    # -------- 4. 高匹配：算法工程师 vs AI 算法岗 --------
    {
        "id": "high_match_ai",
        "resume_text": """
赵六
教育: 博士，人工智能
工作年限: 3 年

技能：Python, PyTorch, TensorFlow, NLP, LLM, LangChain, CUDA

工作经历：
- 某 AI 公司 算法工程师 (2021-2024)
  负责大模型微调与应用
  落地过 RAG 检索增强生成系统，接入过 GPT-4
""",
        "jd": """
招聘 LLM 应用算法工程师
要求：
- 熟悉 NLP / LLM
- 有大模型微调或应用经验
- 熟悉 LangChain / LlamaIndex
- Python + PyTorch
""",
        "ground_truth": {
            "score": 98,
            "strengths": ["博士学历", "LLM实战经验", "RAG落地", "技能完全匹配"],
            "gaps": [],
        },
    },
    # -------- 5. 中低匹配：应届生 vs 要求3年岗 --------
    {
        "id": "low_match_fresh_grad",
        "resume_text": """
孙七
教育: 本科，计算机科学，2024 届应届生

技能：Python, Flask, MySQL, Git
项目经历：在校期间做过图书管理系统（Flask + MySQL）
""",
        "jd": """
招聘 Python 后端工程师
要求：
- 3 年以上开发经验
- 熟悉 FastAPI / Django
- 有高并发系统经验
""",
        "ground_truth": {
            "score": 30,
            "strengths": ["Python 基础"],
            "gaps": ["应届生无工作经验", "仅校园项目无商业经验", "缺高并发经验"],
        },
    },
    # -------- 6. 边界：过度资深（10年） vs 3年岗 --------
    {
        "id": "overqualified",
        "resume_text": """
周八
教育: 硕士
工作年限: 10 年

技能：Python, Java, Go, 架构设计, 团队管理

工作经历：
- 某大厂 技术总监 (2014-2024)
  管理 50 人团队，负责整体技术架构
""",
        "jd": """
招聘 Python 后端工程师
要求：
- 3 年以上 Python 经验
- 负责模块开发
""",
        "ground_truth": {
            "score": 70,
            "strengths": ["技术能力远超要求"],
            "gaps": ["过度资深，可能不愿做执行层开发", "薪资预期可能过高"],
        },
    },
    # -------- 7. 中匹配：全栈 vs 后端岗 --------
    {
        "id": "mid_match_fullstack",
        "resume_text": """
吴九
教育: 本科
工作年限: 4 年

技能：Python, FastAPI, React, PostgreSQL, Docker

工作经历：
- 某创业公司 全栈工程师 (2020-2024)
  独立负责产品前后端开发
""",
        "jd": """
招聘 Python 后端工程师
要求：
- 3 年以上 Python 后端经验
- FastAPI / Django
- PostgreSQL / Redis
- 微服务架构经验
""",
        "ground_truth": {
            "score": 75,
            "strengths": ["FastAPI+PostgreSQL匹配", "4年经验"],
            "gaps": ["全栈背景后端深度可能不足", "无 Redis 提及", "无微服务经验"],
        },
    },
    # -------- 8. 高匹配：运维转 DevOps --------
    {
        "id": "high_match_devops",
        "resume_text": """
郑十
教育: 本科
工作年限: 5 年

技能：Linux, Docker, Kubernetes, CI/CD, Terraform, Ansible, Python

工作经历：
- 某云计算公司 运维工程师 (2019-2024)
  负责 K8s 集群维护与 CI/CD 流水线搭建
  会写 Python 自动化脚本
""",
        "jd": """
招聘 DevOps 工程师
要求：
- 3 年以上运维或 DevOps 经验
- 熟悉 K8s / Docker
- 熟悉 CI/CD 工具（Jenkins / GitLab CI）
- 会写脚本（Python / Shell）
""",
        "ground_truth": {
            "score": 92,
            "strengths": ["5年经验", "K8s+CI/CD 实战", "Python 脚本能力"],
            "gaps": ["未明确提及具体 CI/CD 工具名"],
        },
    },
    # -------- 9. 低匹配：UI 设计师 vs 前端岗 --------
    {
        "id": "low_match_designer",
        "resume_text": """
钱十一
教育: 本科，视觉传达设计
工作年限: 3 年

技能：Figma, Sketch, Photoshop, 会一点 HTML/CSS

工作经历：
- 某设计公司 UI 设计师 (2021-2024)
  负责 App 与网站视觉设计
""",
        "jd": """
招聘前端工程师
要求：
- 3 年以上前端开发经验
- 精通 React / Vue
- JavaScript / TypeScript
""",
        "ground_truth": {
            "score": 20,
            "strengths": ["有UI设计经验便于前端协作"],
            "gaps": ["非开发岗背景", "仅会一点 HTML/CSS", "无 JS 框架经验"],
        },
    },
    # -------- 10. 中高匹配：Node.js 后端 vs 全栈岗 --------
    {
        "id": "mid_high_match_nodejs",
        "resume_text": """
孙十二
教育: 本科
工作年限: 4 年

技能：JavaScript, TypeScript, Node.js, Express, MongoDB, React, Docker

工作经历：
- 某互联网公司 Node.js 后端工程师 (2020-2024)
  负责后端 API 开发，同时支援过前端 React 开发
""",
        "jd": """
招聘全栈工程师
要求：
- 3 年以上开发经验
- 后端: Node.js + Express / Koa
- 前端: React / Vue
- MongoDB / MySQL
""",
        "ground_truth": {
            "score": 85,
            "strengths": ["4年经验", "Node.js+Express+React 完全匹配", "MongoDB 匹配"],
            "gaps": ["无 MySQL 经验"],
        },
    },
]


def get_golden_dataset() -> list[dict]:
    """返回完整黄金数据集。"""
    return GOLDEN_DATASET


__all__ = ["GOLDEN_DATASET", "get_golden_dataset"]
