"""
AI 分析设置页面 — 配置 OpenAI 分析（默认关闭）
"""
from __future__ import annotations

import os

import streamlit as st

from src.ai_analyzer import (
    analyze_reply_with_ai,
    is_ai_available,
    get_model_name,
    SYSTEM_PROMPT,
)
from src import database as db
from src.privacy import prepare_text_for_ai, get_privacy_warnings


def render() -> None:
    """渲染 AI 分析设置页面"""
    st.header("🤖 AI 分析设置")
    st.caption("可选功能：使用 OpenAI API 对导师回复进行深度语义分析。默认关闭。")

    # ── 启用开关 ──
    ai_enabled = st.toggle(
        "启用 AI 分析",
        value=st.session_state.get("ai_enabled", False),
        help="开启后将使用 OpenAI API 分析导师回复，需要有效的 API Key",
    )
    st.session_state["ai_enabled"] = ai_enabled

    if not ai_enabled:
        st.info(
            "💡 AI 分析当前已关闭。所有分析均使用本地规则引擎完成，不发送任何数据到外部。\n\n"
            "如需更精准的语义理解，可开启 AI 分析功能。"
        )
        return

    st.markdown("---")

    # ── 隐私警告 ──
    st.warning(
        "⚠️ **隐私提示**\n\n"
        "启用 AI 分析后，邮件正文摘要（已脱敏处理）将发送到 OpenAI API 进行分析。\n\n"
        "- 发送前会自动移除手机号、身份证号等敏感信息\n"
        "- 正文将被截断至 3000 字以内\n"
        "- API Key 仅在当前会话中使用，不保存到文件\n\n"
        "请确认你了解并同意将邮件内容的摘要发送至第三方 API。"
    )

    consent = st.checkbox(
        "我已了解并同意将脱敏后的邮件内容发送至 OpenAI API",
        value=st.session_state.get("ai_consent", False),
        key="ai_consent_checkbox",
    )
    st.session_state["ai_consent"] = consent

    if not consent:
        st.info("请勾选上方同意后才能使用 AI 分析功能。")
        return

    st.markdown("---")

    # ── API Key & URL 配置 ──
    st.subheader("🔑 API 配置")

    # API Base URL
    env_url = os.environ.get("OPENAI_BASE_URL", "")
    default_url = env_url or st.session_state.get("openai_base_url", "https://api.openai.com/v1")
    
    api_base_url = st.text_input(
        "API 基础 URL (Base URL)",
        value=default_url,
        placeholder="https://api.openai.com/v1",
        help="OpenAI: https://api.openai.com/v1 \n\n"
             "DeepSeek: https://api.deepseek.com \n\n"
             "智谱 GLM: https://open.bigmodel.cn/api/paas/v4 \n\n"
             "使用其他兼容大模型或代理时，在此处修改为相应的 Base URL",
    )
    os.environ["OPENAI_BASE_URL"] = api_base_url
    st.session_state["openai_base_url"] = api_base_url

    # API Key
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key:
        st.success("✅ 已从环境变量 `OPENAI_API_KEY` 读取到 API Key")
        api_key = env_key
    else:
        st.info("💡 未检测到环境变量中的 API Key，请手动输入。")

    manual_key = st.text_input(
        "API Key",
        type="password",
        value="" if env_key else st.session_state.get("openai_api_key", ""),
        placeholder="请输入 API Key",
        help="支持 OpenAI (sk-...)、DeepSeek、智谱、Claude、Gemini 等各大兼容平台的 API Key",
        disabled=bool(env_key),
    )

    if manual_key and not env_key:
        os.environ["OPENAI_API_KEY"] = manual_key
        st.session_state["openai_api_key"] = manual_key
        api_key = manual_key
    elif env_key:
        api_key = env_key
    else:
        api_key = ""

    # ── 模型选择 ──
    st.subheader("🧠 模型选择")

    models = ["gpt-4o-mini", "gpt-4o", "deepseek-chat", "glm-4", "claude-3-5-sonnet", "gemini-1.5-flash", "自定义模型"]
    current_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    selected_model_idx = 0
    if current_model in models:
        selected_model_idx = models.index(current_model)
    elif current_model:
        selected_model_idx = models.index("自定义模型")

    selected_model_choice = st.selectbox(
        "选择预设模型",
        options=models,
        index=selected_model_idx,
        help="如果是自定义供应商，请选择「自定义模型」并手动输入模型名称",
    )

    if selected_model_choice == "自定义模型":
        custom_model = st.text_input(
            "自定义模型名称",
            value=current_model if current_model not in models else "deepseek-chat",
            placeholder="例如: deepseek-chat, qwen-max 等",
            help="请输入服务商提供的准确模型 ID",
        )
        selected_model = custom_model
    else:
        selected_model = selected_model_choice

    os.environ["OPENAI_MODEL"] = selected_model
    st.session_state["openai_model"] = selected_model

    st.markdown("---")

    # ── 分析导师 ──
    st.subheader("🔬 分析导师回复")

    account_id = st.session_state.get("account_id")
    if not account_id:
        st.warning("⚠️ 请先完成邮箱连接和扫描。")
        return

    if not api_key:
        st.warning("⚠️ 请先配置有效的 API Key。")
        return

    teachers = db.get_all_teachers(account_id)
    if not teachers:
        st.info("💡 暂无导师数据，请先在「导师总表」页面运行分析。")
        return

    # 选择导师
    teacher_options = {
        f"{t['name']} — {t.get('institution', '未知')}": t["id"]
        for t in teachers
    }

    selected_teachers = st.multiselect(
        "选择要分析的导师（可多选）",
        options=list(teacher_options.keys()),
        help="选择需要使用 AI 进行深度分析的导师",
    )

    # ── 预览发送内容 ──
    if selected_teachers:
        st.markdown("---")
        st.subheader("👁️ 发送内容预览")
        st.caption("以下为发送给 AI 的脱敏文本预览：")

        user_email = st.session_state.get("email_addr", "")

        for label in selected_teachers:
            tid = teacher_options[label]
            teacher_msgs = db.get_teacher_messages(tid)

            # 提取回复正文
            reply_bodies = []
            for msg in teacher_msgs:
                if not msg.get("is_sent_by_me") and not msg.get("is_auto_reply"):
                    body = msg.get("body_text", "") or msg.get("body_html_text", "")
                    if body.strip():
                        reply_bodies.append(body)

            if reply_bodies:
                preview_text = prepare_text_for_ai(
                    "\n---\n".join(reply_bodies), user_email
                )
                with st.expander(f"📄 {label}", expanded=False):
                    # 隐私警告
                    warnings = get_privacy_warnings(preview_text)
                    if warnings:
                        st.warning("脱敏后仍包含: " + ", ".join(warnings))
                    st.text_area(
                        "预览",
                        value=preview_text,
                        height=200,
                        disabled=True,
                        key=f"preview_{tid}",
                        label_visibility="collapsed",
                    )
            else:
                with st.expander(f"📄 {label}", expanded=False):
                    st.info("该导师暂无回复邮件，无需 AI 分析。")

    # ── 执行分析 ──
    if selected_teachers:
        st.markdown("---")
        if st.button("🚀 开始 AI 分析", type="primary", use_container_width=True):
            user_email = st.session_state.get("email_addr", "")
            progress = st.progress(0, text="正在分析……")
            success_count = 0
            total = len(selected_teachers)

            for i, label in enumerate(selected_teachers):
                tid = teacher_options[label]
                teacher_msgs = db.get_teacher_messages(tid)

                progress.progress(
                    (i + 1) / total,
                    text=f"正在分析 {label}……({i+1}/{total})",
                )

                # 提取回复正文
                reply_bodies = []
                for msg in teacher_msgs:
                    if not msg.get("is_sent_by_me") and not msg.get("is_auto_reply"):
                        body = msg.get("body_text", "") or msg.get("body_html_text", "")
                        if body.strip():
                            reply_bodies.append(body)

                if not reply_bodies:
                    continue

                full_body = "\n---\n".join(reply_bodies)

                try:
                    result = analyze_reply_with_ai(
                        full_body,
                        teacher_name=label.split(" — ")[0],
                        user_email=user_email,
                        api_key=api_key,
                        base_url=api_base_url,
                        model=selected_model,
                    )

                    if result:
                        # 保存分析结果
                        db.insert_analysis({
                            "teacher_id": tid,
                            "analysis_type": "ai",
                            "reply_status": "",
                            "reply_summary": result.reply_summary,
                            "evidence_sentences": "|".join(result.evidence_sentences),
                            "admission_intent": result.admission_intent.value,
                            "action_required": result.action_required.value,
                            "recommended_next_step": result.recommended_next_step,
                            "actual_responder_role": result.actual_responder_role,
                            "confidence": result.confidence,
                            "ambiguity_reason": result.ambiguity_reason,
                            "my_reply_status": "",
                            "model_name": selected_model,
                            "analysis_time": "",
                            "input_hash": "",
                        })
                        success_count += 1
                        st.success(f"✅ {label}: {result.reply_summary[:100]}")
                    else:
                        st.warning(f"⚠️ {label}: AI 分析未返回结果")

                except Exception as e:
                    st.error(f"❌ {label}: {type(e).__name__}")

            progress.progress(1.0, text="分析完成！")
            st.success(f"✅ AI 分析完成！成功分析 {success_count}/{total} 位导师。")
            st.info("💡 请返回「导师总表」重新运行分析，AI 结果将自动整合到总表中。")
