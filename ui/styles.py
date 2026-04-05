import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #0b0b0d;
            color: white;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 5.5rem;
            padding-bottom: 1.5rem;
        }

        .app-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            height: 78px;
            display: flex;
            align-items: center;
            padding: 0 32px;
            background: rgba(11, 11, 13, 0.92);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }

        .brand {
            font-size: 2.1rem;
            font-weight: 750;
            color: white;
            letter-spacing: -0.03em;
        }

        .empty-state {
            min-height: calc(100vh - 260px);
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .empty-title {
            font-size: 3.1rem;
            font-weight: 700;
            color: white;
            letter-spacing: -0.035em;
            margin-bottom: 0.8rem;
            line-height: 1.08;
        }

        .empty-subtitle {
            color: #a7a7ad;
            font-size: 1.14rem;
            line-height: 1.65;
            max-width: 760px;
            margin: 0 auto;
        }

        .chat-container {
            margin-top: 0.5rem;
            margin-bottom: 1.5rem;
        }

        .message-row {
            display: flex;
            width: 100%;
            margin-bottom: 14px;
        }

        .user-row {
            justify-content: flex-end;
        }

        .assistant-row {
            justify-content: flex-start;
        }

        .chat-bubble {
            display: inline-block;
            width: auto;
            max-width: min(720px, 72%);
            padding: 12px 16px;
            border-radius: 18px;
            line-height: 1.55;
            font-size: 1rem;
            white-space: pre-wrap;
            word-break: break-word;
            box-sizing: border-box;
        }

        .user-bubble {
            background: #1f2937;
            border: 1px solid #374151;
            color: white;
            border-bottom-right-radius: 8px;
        }

        .assistant-bubble {
            background: #111214;
            border: 1px solid #23242a;
            color: white;
            border-bottom-left-radius: 8px;
        }

        .helper-text {
            text-align: center;
            color: #8f8f95;
            font-size: 0.95rem;
            margin-top: 0.7rem;
            margin-bottom: 1rem;
        }

        /* ---- chat input wrapper ---- */
        div[data-testid="stChatInput"] {
            width: 100% !important;
            max-width: 920px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            background: transparent !important;
        }

        div[data-testid="stChatInput"] > div {
            width: 100% !important;
            max-width: 920px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            background: transparent !important;
            padding-top: 0 !important;
        }

        div[data-testid="stChatInput"] form {
            width: 100% !important;
        }

        /* главный rounded контейнер */
        div[data-testid="stChatInput"] form > div {
            display: flex !important;
            align-items: center !important;
            gap: 10px !important;
            padding: 0 10px 0 14px !important;
            min-height: 58px !important;
            background: #1a1b20 !important;
            border: 1px solid #2f2f36 !important;
            border-radius: 24px !important;
            box-sizing: border-box !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* убрать внутренние рамки streamlit */
        div[data-testid="stChatInput"] [data-testid="stChatInputTextArea"] {
            flex: 1 1 auto !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        div[data-testid="stChatInput"] [data-testid="stChatInputTextArea"] > div {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
            margin: 0 !important;
            padding: 0 !important;
            border-radius: 0 !important;
        }

        div[data-testid="stChatInput"] [data-testid="stChatInputTextArea"] * {
            box-shadow: none !important;
            outline: none !important;
        }

        /* сам textarea должен быть прозрачным и без своей рамки */
        div[data-testid="stChatInput"] textarea {
            width: 100% !important;
            background: transparent !important;
            color: white !important;
            border: none !important;
            outline: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            resize: none !important;
            box-sizing: border-box !important;

            font-size: 1.02rem !important;
            line-height: 1.35 !important;

            min-height: 58px !important;
            max-height: 140px !important;

            padding: 16px 0 !important;
            margin: 0 !important;
        }

        div[data-testid="stChatInput"] textarea:focus,
        div[data-testid="stChatInput"] textarea:focus-visible,
        div[data-testid="stChatInput"] textarea:active {
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] textarea::placeholder {
            color: #8f8f95 !important;
            opacity: 1 !important;
        }

        /* иногда streamlit красит фокус через родительский элемент */
        div[data-testid="stChatInput"] form > div:focus-within {
            border: 1px solid #2f2f36 !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* кнопка справа */
        div[data-testid="stChatInput"] button {
            flex: 0 0 44px !important;
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            margin: 0 !important;
            padding: 0 !important;
            align-self: center !important;

            border-radius: 999px !important;
            border: 1px solid #323544 !important;
            background: #111827 !important;
            color: white !important;
            box-shadow: none !important;
            outline: none !important;
        }

        div[data-testid="stChatInput"] button:hover {
            background: #172033 !important;
            color: white !important;
        }

        div[data-testid="stChatInput"] button:focus,
        div[data-testid="stChatInput"] button:focus-visible,
        div[data-testid="stChatInput"] button:active {
            box-shadow: none !important;
            outline: none !important;
        }

        .bottom-spacer {
            height: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )