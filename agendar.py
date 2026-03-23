import subprocess
import os
from time import sleep
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

# Cria pasta data se não existir para o log
data_dir = os.path.join(os.path.abspath('.'), 'data')
os.makedirs(data_dir, exist_ok=True)

logging.basicConfig(level=logging.INFO, filemode='w', format='%(asctime)s - %(levelname)s - %(message)s', filename=os.path.join(data_dir, 'log_agendamento.log'))

def main():
    try:
        # Define os caminhos relativos ao local onde este script está rodando
        base_path = os.path.abspath('.')
        
        # O bat e o xml estão dentro da pasta data/
        bat_path = os.path.abspath(os.path.join('data', 'run_bot.bat'))
        xml_path = os.path.abspath(os.path.join('data', 'RPA_INSS_Agendamento.xml'))

        def parse_xml(xml_file):
            namespace = {'ns': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
            ET.register_namespace('', 'http://schemas.microsoft.com/windows/2004/02/mit/task')

            # Na leitura do XML do schtasks do Windows (normalmente UTF-16 LE com BOM)
            try:
                with open(xml_file, 'r', encoding='utf-16') as f:
                    xml_string = f.read()
            except UnicodeDecodeError:
                # Fallback se tiver ficado salvo em UTF-8
                with open(xml_file, 'r', encoding='utf-8') as f:
                    xml_string = f.read()
            
            # Corrige a tag no topo caso o parser do string tenha problemas de conflito
            xml_string = xml_string.replace('encoding="UTF-16"', 'encoding="UTF-8"')
            xml_string = xml_string.replace("encoding='utf-16'", 'encoding="UTF-8"')
            
            from io import StringIO
            tree = ET.parse(StringIO(xml_string))
            root = tree.getroot()
            
            # Buscar a tag StartBoundary (Suporta tanto CalendarTrigger como TimeTrigger)
            start = root.find('.//ns:Triggers/ns:CalendarTrigger/ns:StartBoundary', namespace)
            if start is None:
                start = root.find('.//ns:Triggers/ns:TimeTrigger/ns:StartBoundary', namespace)
                
            comando = root.find('.//ns:Actions/ns:Exec/ns:Command', namespace)
            work_dir = root.find('.//ns:Actions/ns:Exec/ns:WorkingDirectory', namespace)

            # --- CORREÇÃO IMPORTANTE ---
            # Define o horário fixo de 08:30 (Oito e meia) da manhã usando a data de hoje. 
            if start is not None:
                data = datetime.now().strftime('%Y-%m-%dT08:30:00')
                start.text = data
                
            if comando is not None:
                comando.text = bat_path
                
            if work_dir is not None:
                work_dir.text = base_path

            # Grava no formato UTF-16 exigido pelo Agendador do Windows
            xml_out = ET.tostring(root, encoding='utf-16', xml_declaration=True).decode('utf-16')
            with open(xml_file, 'w', encoding='utf-16') as f:
                f.write(xml_out)

        # 1. Ajustar o XML
        parse_xml(xml_path)
        logging.info("XML de agendamento reconfigurado com os caminhos atuais e horário 08:30.")

        # 2. Ajustar o arquivo .bat com o caminho base correto
        if os.path.exists(bat_path):
            with open(bat_path, 'r', encoding='UTF-8') as file:
                linhas = file.readlines()

            mod_line_cd = f'cd /d "{base_path}"\n'
            for i, l in enumerate(linhas):
                if 'cd /d' in l and l != mod_line_cd:
                    linhas[i] = mod_line_cd

            with open(bat_path, 'w', encoding='UTF-8') as file:
                file.writelines(linhas)
            logging.info("Arquivo bat reconfigurado com sucesso.")

        # 3. Criar a tarefa no Windows
        task_name = 'Bot_INSS_Agendamento'
        
        # Cria/sobrescreve a tarefa a partir do xml
        cmd_ag = f'schtasks /create /tn "{task_name}" /xml "{xml_path}" /f'
        subprocess.run(cmd_ag, shell=True)
        logging.info(f"Tarefa {task_name} criada com sucesso no Task Scheduler.")

        print("Agendamento configurado com sucesso! A tarefa roda diariamente as 08:30 da manha.")

    except Exception as e:
        logging.exception(e)
        print(f"Erro ao agendar: {e}. Verifique o data/log_agendamento.log")

if __name__ == '__main__':
    main()
