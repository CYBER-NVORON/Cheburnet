with open('cheburnet/app/ui/widgets/sidebar.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('Главная (VLESS)', 'Главная')
text = text.replace('Правила (beta)', 'Правила')
text = text.replace('Журнал (debug)', 'Журнал')

with open('cheburnet/app/ui/widgets/sidebar.py', 'w', encoding='utf-8') as f:
    f.write(text)
