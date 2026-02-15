import os
from pathlib import Path

print('CWD:', Path.cwd())
try:
    import db
    print('DB_PATH:', db.DB_PATH)
    print('DB exists before init?', Path(db.DB_PATH).exists())
    db.init_db()
    print('DB exists after init?', Path(db.DB_PATH).exists())
except Exception as e:
    print('DB test error:', repr(e))

print('\nOPENAI env check:')
print('OPENAI_API_KEY set?', bool(os.getenv('OPENAI_API_KEY')))
try:
    import llm
    print('Imported llm module OK')
except Exception as e:
    print('llm import error:', repr(e))

print('\nSmoke test complete.')
