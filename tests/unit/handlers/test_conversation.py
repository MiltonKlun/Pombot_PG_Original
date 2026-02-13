import pytest
from telegram.ext import ConversationHandler, CommandHandler
from handlers.conversation import conv_handler
from constants import MAIN_MENU, ADD_SALE_CHOOSE_CATEGORY

def test_conversation_handler_entry_points():
    """Verify the conversation handler starts with /start."""
    entry_points = conv_handler.entry_points
    assert len(entry_points) > 0
    assert isinstance(entry_points[0], CommandHandler)
    assert "start" in entry_points[0].commands

def test_conversation_handler_states():
    """Verify the conversation handler has the expected states."""
    states = conv_handler.states
    
    # Check for key states
    assert MAIN_MENU in states
    assert ADD_SALE_CHOOSE_CATEGORY in states
    
    # Check that states have handlers
    assert len(states[MAIN_MENU]) > 0
    assert len(states[ADD_SALE_CHOOSE_CATEGORY]) > 0

def test_conversation_handler_fallbacks():
    """Verify the conversation handler has a cancel fallback."""
    fallbacks = conv_handler.fallbacks
    assert len(fallbacks) > 0
    # Assuming the fallback is a CommandHandler for 'cancelar'
    found_cancel = False
    for fb in fallbacks:
        if isinstance(fb, CommandHandler) and "cancelar" in fb.commands:
            found_cancel = True
            break
    assert found_cancel, "Fallback for 'cancelar' not found"

def test_conversation_handler_persistence():
    """Verify the conversation handler is persistent."""
    assert conv_handler.persistent is True
    assert conv_handler.name == "pombot_conversation"
