# import pytest

# from app.logic.answer_generation_llm import generate_user_answer_with_llm


# @pytest.mark.asyncio
# async def test_generate_user_answer_with_llm_falls_back_on_error(monkeypatch):
#     def fake_client():
#         raise RuntimeError("boom")

#     monkeypatch.setattr("app.logic.answer_generation_llm._gemini_client", fake_client)

#     payload = {
#         "need_clarification": True,
#         "questions": ["В каком городе искать?"],
#         "request_summary": None,
#         "results_count": 0,
#         "top_results": [],
#     }

#     out = await generate_user_answer_with_llm(payload, use_fallback_on_error=True)

#     assert "В каком городе искать?" in out