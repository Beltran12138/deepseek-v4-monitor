import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import scorer

def test_detect_target_deepseek():
    assert scorer.detect_target("DeepSeek V5 released") == "deepseek"

def test_detect_target_openai():
    assert scorer.detect_target("GPT-5 benchmark results") == "openai"

def test_detect_target_none():
    assert scorer.detect_target("unrelated news today") is None

def test_rule_score_arxiv():
    assert scorer.rule_score("arxiv") == 5

def test_rule_score_unknown():
    assert scorer.rule_score("unknown_source") == 0

def test_score_signal_gray():
    result = scorer.score_signal("twitter", "some tweet", llm_calls_today=0)
    assert result["level"] == "gray"
    assert result["rule_score"] == 1
    assert result["llm_score"] is None

def test_score_signal_yellow():
    result = scorer.score_signal("github_new_branch", "v5 branch detected", llm_calls_today=0)
    assert result["level"] == "yellow"
    assert result["rule_score"] == 4

def test_score_signal_no_llm_when_quota_full():
    result = scorer.score_signal("arxiv", "deepseek v5 paper", llm_calls_today=999)
    assert result["level"] == "yellow"
    assert result["llm_score"] is None
