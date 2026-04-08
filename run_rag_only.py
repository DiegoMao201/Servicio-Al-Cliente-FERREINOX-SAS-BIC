"""Run only RAG portion of test_super_agent.py"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
exec(compile(open('test_super_agent.py', encoding='utf-8').read().split('def run_agent_tests')[0], 'test_super_agent.py', 'exec'))
print('Starting RAG tests...')
run_rag_tests()
