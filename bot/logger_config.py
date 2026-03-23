import logging
import os
import sys

def setup_logger():
    """
    Configura o sistema de logs local.
    Salva os logs detalhados (DEBUG/INFO/ERROR) num arquivo 'execucao.log' na pasta data,
    e também imprime no console.
    """
    logger = logging.getLogger("BotINSS")
    
    # Previne adicionar múltiplos handlers se for chamado de novo
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.DEBUG)

    # Identifica pasta do sistema (para escrever o .log sempre em local seguro)
    if getattr(sys, 'frozen', False):
        base_dir_app = os.path.dirname(sys.executable)
    else:
        base_dir_app = os.path.abspath(os.getcwd())

    log_dir = os.path.join(base_dir_app, "data")
    os.makedirs(log_dir, exist_ok=True)
    caminho_log = os.path.join(log_dir, "execucao.log")
    
    # No começo de cada nova execução global, opcionalmente limpamos o log antigo?
    # Para suportar suporte histórico, melhor usar append mode ('a') com um marco de inicio!
    # Mas se quiser um arquivo novo todo dia: mode='w'
    file_handler = logging.FileHandler(caminho_log, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    # No console deixamos INFO para não poluir muito a tela preta
    console_handler.setLevel(logging.INFO)

    # Formatação detalhada para o arquivo (.log) - incluindo classe/funçao e linha se erro
    file_formatter = logging.Formatter('%(asctime)s | %(levelname)8s | %(filename)s:%(lineno)d | %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
    file_handler.setFormatter(file_formatter)

    # Formatação mais limpa pro Console
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger, caminho_log
