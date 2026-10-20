$env:PYTHONPYCACHEPREFIX = "$env:TEMP\pyc_cache"
$env:PYTHONWARNINGS = "ignore"
& D:\pythonproject\knowledgeforge\.venv\Scripts\python.exe scripts\rehash_questions.py @args 2>&1 |
    Where-Object { $_ -notmatch 'sqlalchemy|pymysql|INFO' } |
    Out-String -Width 250
