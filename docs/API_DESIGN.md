# API 设计 (API Design)

## 1. 全局约定

- 基础路径: `/api/v1`
- 认证: 暂不启用（练手项目），后续可加 API Key
- 响应格式: `application/json`
- 错误格式: `{"detail": "...", "code": "..."}`

## 2. 接口列表

### 2.1 简历解析 `/api/v1/resumes`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/resumes/upload` | 上传简历文件并解析 |
| GET | `/api/v1/resumes` | 获取所有简历列表 |
| GET | `/api/v1/resumes/{resume_id}` | 获取单份简历详情 |
| PUT | `/api/v1/resumes/{resume_id}` | 更新简历信息（人工修正 |
| DELETE | `/api/v1/resumes/{resume_id}` | 删除简历 |

### 2.2 岗位匹配 `/api/v1/matches`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/matches/single` | 单份简历 vs JD 匹配 |
| POST | `/api/v1/matches/batch` | 多份简历 vs 同一 JD 批量匹配 & 排序 |

### 2.3 简历优化 `/api/v1/optimize`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/optimize/suggestions` | 生成优化建议 |
| POST | `/api/v1/optimize/rewrite` | 针对某段落重写 |

### 2.4 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/docs` | Swagger UI |

## 3. 请求/响应示例

### POST /api/v1/resumes/upload

**Request** (multipart/form-data):
```
file: resume.pdf
```

**Response** (201):
```json
{
  "resume_id": "550e8400-e29b-41d4-a716-446655440000",
  "parsed": {
    "name": "张三",
    "email": "zhangsan@example.com",
    "education_level": "硕士",
    "years_of_experience": 5.5,
    "skills": ["Python", "FastAPI", "SQL", "Docker"],
    "work_history": [
      {
        "company": "ABC 公司",
        "role": "后端工程师",
        "period": "2022.03 - 至今",
        "highlights": ["..."]
      }
    ]
  }
}
```

### POST /api/v1/matches/single

**Request**:
```json
{
  "resume_id": "550e8400-e29b-41d4-a716-446655440000",
  "jd": "岗位描述：3 年以上 Python 后端经验，熟悉 FastAPI..."
}
```

**Response**:
```json
{
  "match_id": "...",
  "overall_score": 85.5,
  "breakdown": {
    "skill_match": 90,
    "experience_match": 80,
    "education_match": 85
  },
  "strengths": ["FastAPI 经验丰富", "团队协作突出"],
  "gaps": ["缺少云原生经验"]
}
```
