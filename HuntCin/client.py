"""
HuntCin - Client (Terceira Etapa)
Cliente UDP que comunica com o servidor HuntCin usando RDT 3.0.
Funcionalidades:
 - login <nome>
 - logout
 - move <up/down/left/right>
 - hint
 - suggest
Observações:
 - Rodar vários clientes (terminal separados) para testar multiplayer.
"""

import socket
import threading
import sys

# --- Configurações ---
SERVER_IP = "127.0.0.1"
SERVER_PORT = 62451
TIMEOUT = 3.0
BUFFER_SIZE = 4096

ACK0 = b'ACK0'
ACK1 = b'ACK1'

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Bind na porta 0 deixa o SO escolher uma livre
client.bind(("127.0.0.1", 0)) 
client.settimeout(0.5)

# --- Estado RDT ---
seq_send = 0
seq_recv = 0
ack_events = {0: threading.Event(), 1: threading.Event()}
running = True

def make_pkt(seq, data):
    return str(seq).encode() + b'|' + data.encode()

def extract_pkt(pkt):
    try:
        sep = pkt.find(b'|')
        if sep < 0: return None, None
        return int(pkt[:sep]), pkt[sep+1:]
    except:
        return None, None

def send_reliable(msg):
    """Envia o comando e espera o ACK do protocolo (técnico)."""
    global seq_send
    pkt = make_pkt(seq_send, msg)
    ack_events[seq_send].clear()
    
    # Tenta enviar até receber o ACK
    while True:
        try:
            client.sendto(pkt, (SERVER_IP, SERVER_PORT))
        except Exception as e:
            print(f"Erro envio: {e}")

        # Aguarda ACK específico desse pacote
        if ack_events[seq_send].wait(TIMEOUT):
            # Recebeu ACK, inverte bit e retorna sucesso
            seq_send = 1 - seq_send
            return True
        
        print(f" [RDT] Timeout esperando ACK{seq_send}... Reenviando.")

def receiver_thread():
    """Escuta respostas do servidor (Erros, Broadcasts, Logs)."""
    global seq_recv
    print(f"Cliente iniciado na porta {client.getsockname()[1]}")
    
    while running:
        try:
            data, _ = client.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            continue
        except:
            break

        # Se for ACK do servidor (confirmando nosso envio)
        if data == ACK0:
            ack_events[0].set()
            continue
        if data == ACK1:
            ack_events[1].set()
            continue
            
        # Se for Dado vindo do servidor (Mensagem de erro, Broadcast, etc)
        s, content = extract_pkt(data)
        if s is not None:
            # Envia ACK de volta pro servidor parar de encher o saco
            reply = ACK0 if s == 0 else ACK1
            client.sendto(reply, (SERVER_IP, SERVER_PORT))
            
            # Verifica se é a sequência esperada (evita duplicação)
            if s == seq_recv:
                seq_recv = 1 - seq_recv
                try:
                    texto = content.decode()
                    # Imprime a mensagem do servidor
                    print(f"\n{texto}")
                    # Restaura o prompt visualmente
                    print("> ", end="", flush=True)
                except:
                    pass

if __name__ == "__main__":
    t = threading.Thread(target=receiver_thread, daemon=True)
    t.start()
    
    print("\n--- HuntCin Client ---")
    print("Comandos: login <nome>, logout, move <up/down/left/right>, hint, suggest")
    
    while True:
        try:
            # Lê comando
            cmd = input("> ").strip()
            if not cmd: continue
            
            if cmd == "exit": 
                break
            
            send_reliable(cmd)
            
        except KeyboardInterrupt:
            break
            
    running = False
    client.close()
    print("Cliente encerrado.")