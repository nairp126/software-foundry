content = open('tests/test_e2e.py').read()
old = 'with patch("foundry.main.get_db", return_value=_iter_session(session)):'
new = 'async with _override_db(session):'
count = content.count(old)
content = content.replace(old, new)
open('tests/test_e2e.py', 'w').write(content)
print(f'Replaced {count} occurrences')
print(f'Remaining foundry.main.get_db refs: {content.count("foundry.main.get_db")}')
