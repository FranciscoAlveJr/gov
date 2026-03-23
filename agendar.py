import subprocess
import os
from time import sleep
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, filemode='w', format='%(asctime)s - %(levelname)s - %(message)s', filename='log_agendamento.log')

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

            # Lê o texto e remove/ajusta a declaração de encoding que quebra o parse
            with open(xml_file, 'r', encoding='utf-8') as f:
                xml_string = f.read()
            
            # Se tiver UTF-16 no cabeçalho mas o arquivo for UTF-8 (comum ao exportar)
            xml_string = xml_string.replace('encoding="UTF-16"', 'encoding="UTF-8"')
            
            from io import StringIO
            tree = ET.parse(StringIO(xml_string))
            root = tree.getroot()
            
            # Note que XML originado do Windows possui namespace padrão
            start = root.find('.//ns:Triggers/ns:CalendarTrigger/ns:StartBoundary', namespace)
            if start is None:
                # Caso use TimeTrigger de alguma forma alternativa
                start = root.find('.//ns:Triggers/ns:TimeTrigger/ns:StartBoundary', namespace)
                
            comando = root.find('.//ns:Actions/ns:Exec/ns:Command', namespace)
            work_dir = root.find('.//ns:Actions/ns:Exec/ns:WorkingDirectory', namespace)

            # Define a data do próximo disparo para agora + 1 ou ajusta apenas o formato
            if start is not None:
                data = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                start.text = data
                
            if comando is not None:
                comando.text = bat_path
                
            if work_dir is not None:
                work_dir.text = base_path

            # Salva no formato que o Windows espera em Agendador de Tarefas
            xml_out = ET.tostring(root, encoding='utf-16', xml_declaration=True).decode('utf-16')
            with open(xml_file, 'w', encoding='utf-16') as f:
                f.write(xml_out)

        # 1. Ajustar o XML
        parse_xml(xml_path)
        logging.info("XML de agendamento reconfigurado com os caminhos atuais.")

        # 2. Ajustar o arquivo .bat com o caminho base correto
        with open(bat_path, 'r', encoding='UTF-8') as file:
            linhas = file.readlines()

        mod_line_cd = f'cd /d "{base_path}"\n'
        for i, l in enumerate(linhas):
            if 'cd /d' in l and l != mod_line_cd:
                linhas[i] = mod_line_cd

        with open(bat_path, 'w', encoding='UTF-8') as file:
            file.writelines(linhas)
            
        logging.info("Aquivo bat reconfigurado com sucesso.")

        # 3. Criar a tarefa no Windows
        task_name = 'Bot_INSS_Agendamento'
        
        # Cria (ou sobrescreve caso exista) a tarefa a partir do xml
        cmd_ag = f'schtasks /create /tn "{task_name}" /xml "{xml_path}" /f'
        subprocess.run(cmd_ag, shell=True)
        logging.info(f"Tarefa {task_name} criada com sucesso no Task Scheduler.")

        sleep(1)

        # 4. Executar a tarefa (opcional: comente caso só queira agendar)
        cmd_run = f'schtasks /run /tn "{task_name}"'
        subprocess.run(cmd_run, shell=True)
        logging.info("Tarefa enviada para execução inicial.")
        
        print("Agendamento e configuração concluídos com sucesso!")

    except Exception as e:
        logging.exception(e)
        print(f"Erro ao agendar: {e}")

if __name__ == '__main__':
    main()
