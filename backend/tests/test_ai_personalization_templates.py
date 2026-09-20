from types import SimpleNamespace

from app.db.schema import SCHEMA_STATEMENTS
from app.schemas.inspiration import (
    InspirationPersonalizationTemplateCreate,
    InspirationSessionCreate,
)
from app.services.inspiration_service import (
    InspirationService,
    build_assistant_identity_reply,
)


def test_normal_mode_prompt_is_general_and_ignores_creative_context():
    service = InspirationService(SimpleNamespace())

    prompt = service._system_prompt(
        {
            "interaction_mode": "normal",
            "goal_type": "topic",
            "tone": "小红书爆款语气",
            "linked_product_name": "测试产品",
            "extra_requirement": "输出小红书笔记",
        }
    )

    assert "通用 AI 助手" in prompt
    assert "不要默认用户正在讨论小红书" in prompt
    assert "小红书爆款语气" not in prompt
    assert "测试产品" not in prompt
    assert "输出小红书笔记" not in prompt


def test_normal_mode_context_does_not_load_product_or_creative_settings():
    service = InspirationService(SimpleNamespace())

    context = service._context_from_session(
        {
            "title": "日常问答",
            "interaction_mode": "normal",
            "linked_product_id": 99,
            "linked_xhs_account_id": 88,
            "personalization_template_id": 77,
            "goal_type": "topic",
            "tone": "小红书爆款语气",
            "extra_requirement": "输出种草笔记",
        }
    )

    assert context == {
        "session_title": "日常问答",
        "linked_product_id": 0,
        "linked_product_name": "",
        "linked_xhs_account_id": 0,
        "interaction_mode": "normal",
        "personalization_template_id": 0,
        "goal_type": "general",
        "tone": "",
        "extra_requirement": "",
    }


def test_normal_identity_reply_is_not_positioned_as_xiaohongshu_assistant():
    reply = build_assistant_identity_reply(interaction_mode="normal")

    assert "通用 AI 助手" in reply
    assert "小红书" not in reply
    assert "个性化档案" not in reply


def test_personalized_session_requires_and_keeps_template_identifier():
    template = InspirationPersonalizationTemplateCreate(
        template_name="运营顾问",
        assistant_name="小禾",
        assistant_traits="专业、直接",
    )
    session = InspirationSessionCreate(
        title="新品讨论",
        interaction_mode="personalized",
        personalization_template_id=42,
    )

    assert template.template_name == "运营顾问"
    assert session.personalization_template_id == 42


def test_normal_session_discards_template_identifier():
    session = InspirationSessionCreate(
        title="日常问答",
        interaction_mode="normal",
        personalization_template_id=42,
    )

    assert session.personalization_template_id == 0


def test_schema_declares_personalization_templates_preferences_and_session_binding():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "create table if not exists ai_personalization_template" in schema
    assert "create table if not exists ai_chat_preference" in schema
    assert "personalization_template_id bigint unsigned not null default 0" in schema


def test_session_list_forwards_conversation_space_filters():
    service = InspirationService(SimpleNamespace())
    calls: list[tuple] = []
    service.repository = SimpleNamespace(
        list_sessions_for_user=lambda *args: calls.append(args) or {
            "items": [],
            "page": 1,
            "page_size": 20,
            "total": 0,
        }
    )

    service.list_sessions(
        {"tenant_id": 7, "id": 9},
        1,
        20,
        interaction_mode="personalized",
        personalization_template_id=42,
    )

    assert calls == [(7, 9, 1, 20, "personalized", 42)]
