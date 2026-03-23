import os

path = r'bot\browser.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('print(f', 'logger.info(f').replace('print("Erro', 'logger.error("Erro').replace('print(', 'logger.info(')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
