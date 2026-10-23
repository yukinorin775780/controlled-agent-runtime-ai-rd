"""
AFK 闲聊保护性测试。
锁定挂机闲聊 speaker 池不会选择 player / 敌人 / 死亡实体。
"""

import asyncio

from core.graph.nodes.dm import dm_node


def test_idle_banter_skips_when_only_player_is_available():
    state = {
        "intent": "trigger_idle_banter",
        "entities": {
            "player": {
                "name": "玩家",
                "status": "alive",
                "faction": "player",
            }
        },
    }

    result = asyncio.run(dm_node(state))

    assert result == {}


def test_idle_banter_selects_only_living_party_npc():
    state = {
        "intent": "trigger_idle_banter",
        "entities": {
            "player": {"status": "alive", "faction": "player"},
            "analyst": {"status": "alive", "faction": "party"},
            "scout": {"status": "dead", "faction": "party"},
            "drone_1": {"status": "alive", "faction": "hostile"},
            "villager": {"status": "alive", "faction": "neutral"},
        },
    }

    result = asyncio.run(dm_node(state))

    assert result["current_speaker"] == "analyst"
    assert result["intent"] == "trigger_idle_banter"
