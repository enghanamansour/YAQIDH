"""Token use: what a run costs is measured, and the model is told the skills up front (no list_skills step)."""

import httpx

from src.agent.loop import ChatClient
from src.agent.prompt import task_message


def test_the_chat_client_adds_up_the_tokens_the_provider_reports():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "x"}}],
                                         "usage": {"total_tokens": 120}})

    chat = ChatClient(base_url="http://x", api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler)))
    chat.complete([{"role": "user", "content": "hi"}], None)
    chat.complete([{"role": "user", "content": "hi"}], None)
    assert chat.total_tokens == 240


def test_the_task_lists_the_skills_so_the_model_does_not_spend_a_step_asking():
    text = task_message("r1", "push", "security_blocked", ["2 high open"], [{"name": "sql-injection", "description": "SQL from input"}])
    assert "sql-injection: SQL from input" in text
    assert "Skills you can read" not in task_message("r1", "push", "x", [])
