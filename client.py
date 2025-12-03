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
 - PROB_PERDA = 0 por padrão; ajustar para testar perdas.
"""

import socket
import threading
import time
import random
import sys

# --- Configurações ---
SERVER_ADDR = ("127.0.0.1", 5000)
TIMEOUT = 2.0
PROB_PERDA = 0.0
BUFFER_SIZE = 2048
ACK0 = b'ACK0'
ACK1 = b'ACK1'

def make_pkt(seq_num: int, data: bytes) -> bytes:
    return str(seq_num).encode() + b'|' + data

def extract_pkt(packet: bytes):
    sep = packet.find(b'|')
    if sep == -1:
        return None, packet
    try:
        seq = int(packet[:sep].decode())
        return seq, packet[sep+1:]
    except Exception:
        return None, packet

def make_ack_bytes(seq_num: int) -> bytes:
    return ACK0 if seq_num == 0 else ACK1

def simulate_loss() -> bool:
    return random.random() < PROB_PERDA

# --- Estado do cliente ---
cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cliente.bind(("0.0.0.0", 0))  # porta escolhida pelo SO (cada cliente terá porta diferente)
cliente.settimeout(0.5)

expected_seq_recv = 0   # bit que esperamos receber do servidor
next_seq_send = 0       # bit a ser usado para enviar ao servidor
ack_events = {0: threading.Event(), 1: threading.Event()}

logged_in = False
my_name = None
running = True

def send_reliable(message_str):
    """
    Envia mensagem confiável ao servidor usando alternating-bit stop-and-wait.
    A thread receiver sinaliza ack_events quando ACK correspondente chegar.
    """
    global next_seq_send
    payload = message_str.encode()
    while True:
        seq = next_seq_send
        ack_events[seq].clear()
        pkt = make_pkt(seq, payload)
        if simulate_loss():
            print(f"  [SIMULAÇÃO] (client->server) Pacote {seq} PERDIDO (mensagem: {message_str})")
        else:
            try:
                cliente.sendto(pkt, SERVER_ADDR)
            except Exception as e:
                print(f"[RDT-ENVIAR] Erro ao enviar: {e}")
        got = ack_events[seq].wait(TIMEOUT)
        if got:
            next_seq_send = 1 - next_seq_send
            return True
        else:
            print(f"  [RDT-ENVIAR] Timeout esperando ACK{seq} do servidor. Reenviando...")

def send_ack_immediate(seq_num):
    ack = make_ack_bytes(seq_num)
    if simulate_loss():
        print(f"  [SIMULAÇÃO] (client->server) ACK{seq_num} PERDIDO")
    else:
        cliente.sendto(ack, SERVER_ADDR)

def receiver_thread():
    """
    Recebe tudo do servidor:
     - se for ACK puro, sinaliza ack_events.
     - se for pacote com bit|payload, checa expected_seq_recv, envia ACK e exibe payload.
    """
    global expected_seq_recv, logged_in, my_name, running
    while running:
        try:
            packet, addr = cliente.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[RECEPTOR] Erro recv: {e}")
            continue

        if packet == ACK0 or packet == ACK1:
            bit = 0 if packet == ACK0 else 1
            ev = ack_events.get(bit)
            if ev:
                ev.set()
            continue

        seq, data = extract_pkt(packet)
        if seq is None:
            print("[RECEPTOR] Pacote mal formatado do servidor.")
            continue

        if seq == expected_seq_recv:
            send_ack_immediate(seq)
            expected_seq_recv = 1 - expected_seq_recv
            try:
                msg = data.decode()
            except Exception:
                msg = "<dados binários>"
            print(f"\n[Servidor] {msg}\n> ", end="", flush=True)
            if msg.strip().lower() == "você está online!":
                logged_in = True
            if msg.strip().lower().startswith("logout efetuado"):
                logged_in = False
                my_name = None
        else:
            send_ack_immediate(1 - expected_seq_recv)

def interactive_loop():
    """Loop principal para enviar comandos digitados pelo usuário."""
    global logged_in, my_name, running
    print(f"Cliente iniciado. Conectando ao servidor {SERVER_ADDR}. Porta local: {cliente.getsockname()[1]}")
    print("Comandos: login <nome> | logout | move <up/down/left/right> | hint | suggest | exit")
    while True:
        try:
            cmd = input("> ").strip()
        except EOFError:
            cmd = "exit"
        if not cmd:
            continue
        parts = cmd.split()
        if parts[0].lower() == "exit":
            if logged_in:
                send_reliable("logout")
            running = False
            time.sleep(0.2)
            cliente.close()
            print("Cliente finalizado.")
            sys.exit(0)

        if parts[0].lower() == "login":
            if len(parts) < 2:
                print("Uso: login <nome>")
                continue
            name = " ".join(parts[1:])
            my_name = name
            send_reliable(f"login {name}")
            time.sleep(0.2)
            continue

        if parts[0].lower() == "logout":
            if not logged_in:
                print("Você não está logado.")
                continue
            send_reliable("logout")
            logged_in = False
            my_name = None
            continue

        if not logged_in:
            print("Você precisa fazer login primeiro (use: login <nome>)")
            continue

        cmd_low = parts[0].lower()
        if cmd_low == "move":
            if len(parts) != 2 or parts[1].lower() not in ("up", "down", "left", "right"):
                print("Uso: move <up|down|left|right>")
                continue
            send_reliable(f"move {parts[1].lower()}")
            continue
        elif cmd_low == "hint":
            send_reliable("hint")
            continue
        elif cmd_low == "suggest":
            send_reliable("suggest")
            continue
        else:
            print("Comando desconhecido.")

if __name__ == "__main__":
    t = threading.Thread(target=receiver_thread, daemon=True)
    t.start()
    try:
        interactive_loop()
    except KeyboardInterrupt:
        running = False
        cliente.close()
        print("\nInterrupção. Cliente encerrado.")
