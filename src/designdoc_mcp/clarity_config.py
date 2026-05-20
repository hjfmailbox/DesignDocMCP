"""清晰度评估配置模块

集中管理清晰度评估的维度关键词和评分参数，替代硬编码配置。
支持通过环境变量覆盖关键参数。
"""

from __future__ import annotations

import os
from typing import Dict, List

# 维度关键词配置
DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    "core_entities": [
        "entity", "entities", "model", "object", "component", "module", "layer",
        "架构", "模型", "实体", "组件", "模块", "层",
    ],
    "users_and_permissions": [
        "user", "role", "permission", "auth", "access", "sensitivity", "visibility",
        "用户", "权限", "角色", "访问", "敏感",
    ],
    "data_storage": [
        "storage", "database", "store", "persist", "sqlite", "jsonl", "file", "index",
        "存储", "数据库", "持久", "索引",
    ],
    "core_workflow": [
        "workflow", "pipeline", "process", "flow", "ingest", "extract", "retrieve", "query",
        "流程", "管道", "工作流", "检索",
    ],
    "non_functional": [
        "performance", "scalability", "security", "latency", "throughput", "local", "offline",
        "性能", "安全", "扩展", "本地",
    ],
    "integration_and_boundary": [
        "integration", "api", "external", "boundary", "scope", "not include", "not do",
        "集成", "边界", "范围", "不含",
    ],
    "constraints": [
        "constraint", "must", "shall", "required", "never", "forbidden",
        "约束", "必须", "禁止", "不得",
    ],
    "acceptance_criteria": [
        "criteria", "acceptance", "verify", "test", "validate",
        "验收", "标准", "验证", "测试",
    ],
    "tech_stack": [
        "python", "typescript", "react", "sqlite", "docker", "framework", "library",
        "技术栈", "框架", "依赖",
    ],
    "scope_boundary": [
        "scope", "not include", "not do", "out of scope", "mvp", "phase",
        "范围", "不含", "不做", "阶段",
    ],
}

# 评分参数常量（支持环境变量覆盖）
MAX_LENGTH_BONUS = float(os.environ.get("DESIGNDOC_MAX_LENGTH_BONUS", "0.15"))
LENGTH_NORMALIZATION_FACTOR = int(os.environ.get("DESIGNDOC_LENGTH_NORM_FACTOR", "10000"))
FIELD_COMPLETION_BONUS = float(os.environ.get("DESIGNDOC_FIELD_COMPLETION_BONUS", "0.05"))
MAX_CLARITY_SCORE = float(os.environ.get("DESIGNDOC_MAX_CLARITY_SCORE", "1.0"))


def validate_config() -> bool:
    """验证配置的完整性和一致性。

    Returns:
        True 如果配置有效。

    Raises:
        ValueError: 配置存在不一致或参数异常时抛出。
    """
    from .models import CLARITY_DIMENSIONS

    # 检查维度一致性
    configured_dims = set(DIMENSION_KEYWORDS.keys())
    expected_dims = set(CLARITY_DIMENSIONS)
    if configured_dims != expected_dims:
        missing = expected_dims - configured_dims
        extra = configured_dims - expected_dims
        raise ValueError(
            f"维度配置不一致: 缺失维度 {missing}, 多余维度 {extra}"
        )

    # 检查关键词非空
    for dim, keywords in DIMENSION_KEYWORDS.items():
        if not keywords:
            raise ValueError(f"维度 '{dim}' 的关键词列表为空")

    # 检查评分参数合理性
    if not (0 <= MAX_LENGTH_BONUS <= 1):
        raise ValueError(f"MAX_LENGTH_BONUS 必须在 [0, 1] 范围内，当前为 {MAX_LENGTH_BONUS}")
    if LENGTH_NORMALIZATION_FACTOR <= 0:
        raise ValueError(f"LENGTH_NORMALIZATION_FACTOR 必须大于 0，当前为 {LENGTH_NORMALIZATION_FACTOR}")
    if not (0 <= FIELD_COMPLETION_BONUS <= 1):
        raise ValueError(f"FIELD_COMPLETION_BONUS 必须在 [0, 1] 范围内，当前为 {FIELD_COMPLETION_BONUS}")
    if not (0 < MAX_CLARITY_SCORE <= 1):
        raise ValueError(f"MAX_CLARITY_SCORE 必须在 (0, 1] 范围内，当前为 {MAX_CLARITY_SCORE}")

    return True
